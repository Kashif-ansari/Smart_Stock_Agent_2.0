from collections import Counter
from functools import lru_cache
from pathlib import Path
import hashlib,json,math,os,re,shutil,uuid
import numpy as np
from sqlalchemy import select
from src.core.db import session
from src.core.auth import require,allowed,audit
from src.core.models import KnowledgeDoc
from src.core.config import tenant_dir,flag,storage
from .extract import extract,chunk_segments

def permitted_scopes(ctx):
    scopes=['general']
    if allowed(ctx,'finance.read'):scopes.append('finance')
    if allowed(ctx,'hr.read'):scopes.append('hr')
    return scopes

def documents(ctx):
    require(ctx,'knowledge.read')
    with session() as s:return s.scalars(select(KnowledgeDoc).where(KnowledgeDoc.tenant_id==ctx.tenant_id,KnowledgeDoc.scope.in_(permitted_scopes(ctx)))).all()

def add_document(ctx,name,raw,scope='general'):
    require(ctx,'knowledge.write')
    if scope not in permitted_scopes(ctx):raise PermissionError('Restricted knowledge scope.')
    parts=extract(name,raw);key=hashlib.sha256(raw).hexdigest()
    with session() as s:
        if s.scalar(select(KnowledgeDoc).where(KnowledgeDoc.tenant_id==ctx.tenant_id,KnowledgeDoc.scope==scope,KnowledgeDoc.content_hash==key)):raise ValueError('This document is already in this collection.')
        d=KnowledgeDoc(tenant_id=ctx.tenant_id,title=Path(name).name[:200],scope=scope,content_hash=key,payload=parts)
        s.add(d);s.flush();audit(s,ctx,'knowledge.added',{'document_id':d.id,'scope':scope})
        return d.id,len(parts)

def delete_document(ctx,did):
    require(ctx,'admin')
    with session() as s:
        d=s.scalar(select(KnowledgeDoc).where(KnowledgeDoc.tenant_id==ctx.tenant_id,KnowledgeDoc.id==did,KnowledgeDoc.scope.in_(permitted_scopes(ctx))))
        if not d:raise ValueError('Document unavailable.')
        from src.services.lifecycle import clear_derived
        clear_derived(s,ctx)
        scope=d.scope;s.delete(d);audit(s,ctx,'knowledge.deleted',{'document_id':did})
    # Removing this corpus also invalidates its old dense vectors immediately.
    shutil.rmtree(tenant_dir(ctx.tenant_id,'indexes')/scope,ignore_errors=True)

def tokens(text):return re.findall(r'[\w-]+',text.casefold())

def bm25(query,chunks):
    q=tokens(query);docs=[tokens(c['text']) for c in chunks];n=len(docs)
    if not n:return []
    avg=sum(map(len,docs))/n
    freq=Counter(t for d in docs for t in set(d));scores=[]
    for i,d in enumerate(docs):
        count=Counter(d);score=0
        for term in q:
            tf=count[term];idf=math.log(1+(n-freq[term]+.5)/(freq[term]+.5))
            score+=idf*tf*2.5/(tf+1.5*(.25+.75*len(d)/max(avg,1)))
        if score>0:scores.append((i,score))
    return sorted(scores,key=lambda x:x[1],reverse=True)

@lru_cache(maxsize=2)
def embedding_model(model_name):
    if not flag('ENABLE_MODEL_DOWNLOADS'):raise ValueError('Model downloads have not been enabled by the administrator.')
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=model_name,cache_dir=str(storage()/'model_cache'),threads=2)

@lru_cache(maxsize=1)
def reranker_model(model_name):
    if not flag('ENABLE_MODEL_DOWNLOADS'):raise ValueError('Model downloads disabled.')
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(model_name=model_name,cache_dir=str(storage()/'model_cache'),threads=2)

def collect(docs):
    result=[]
    for d in docs:
        for i,c in enumerate(chunk_segments(d.payload)):
            result.append({**c,'id':f'{d.id}:{i}','document_id':d.id,'title':d.title,'scope':d.scope})
    return result

def signature(docs):return hashlib.sha256('|'.join(sorted(d.id+':'+d.content_hash for d in docs)).encode()).hexdigest()

def build_index(ctx,scope='general'):
    require(ctx,'knowledge.write')
    from src.services.lifecycle import purge_revision,ensure_current
    revision=purge_revision(ctx)
    if scope not in permitted_scopes(ctx):raise PermissionError('Restricted corpus.')
    if not flag('ENABLE_SEMANTIC_SEARCH'):raise ValueError('Enable semantic search in server configuration first.')
    docs=[d for d in documents(ctx) if d.scope==scope];chunks=collect(docs)
    if not chunks:raise ValueError('Upload a document to this collection first.')
    modelname=os.getenv('EMBEDDING_MODEL','BAAI/bge-small-en-v1.5')
    embedder=embedding_model(modelname)
    vectors=np.asarray(list(embedder.passage_embed([c['text'] for c in chunks])),dtype='float32')
    import faiss
    faiss.normalize_L2(vectors);index=faiss.IndexFlatIP(vectors.shape[1]);index.add(vectors)
    base=tenant_dir(ctx.tenant_id,'indexes')/scope;base.mkdir(parents=True,exist_ok=True)
    version=str(uuid.uuid4());folder=base/version;folder.mkdir()
    idx=folder/'index.faiss';faiss.write_index(index,str(idx))
    manifest={'version':version,'model':modelname,'dimensions':vectors.shape[1],'signature':signature(docs),'sha256':hashlib.sha256(idx.read_bytes()).hexdigest(),'chunks':chunks,'keyword_tokens':[tokens(c['text']) for c in chunks]}
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    ensure_current(ctx,revision)
    pointer=base/(version+'.tmp');pointer.write_text(version);os.replace(pointer,base/'current')
    with session() as s:audit(s,ctx,'index.built',{'scope':scope,'chunks':len(chunks),'version':version})
    return {'scope':scope,'chunks':len(chunks),'version':version,'model':modelname}

def retrieve(ctx,query,k=6,scopes=None):
    require(ctx,'knowledge.read')
    selected=[scope for scope in permitted_scopes(ctx) if scopes is None or scope in scopes]
    docs=[d for d in documents(ctx) if d.scope in selected];chunks=collect(docs);lookup={c['id']:c for c in chunks};ranks={};notes=[]
    for rank,(ix,_) in enumerate(bm25(query,chunks)[:30],1):ranks[chunks[ix]['id']]=1/(60+rank)
    mode='Keyword search'
    if flag('ENABLE_SEMANTIC_SEARCH'):
        for scope in selected:
            base=tenant_dir(ctx.tenant_id,'indexes')/scope
            if not (base/'current').exists():continue
            try:
                version=(base/'current').read_text().strip();uuid.UUID(version)
                folder=base/version;manifest=json.loads((folder/'manifest.json').read_text())
                scoped=[d for d in docs if d.scope==scope]
                if manifest['signature']!=signature(scoped):notes.append('A collection changed; rebuild its semantic index.');continue
                if manifest['model']!=os.getenv('EMBEDDING_MODEL','BAAI/bge-small-en-v1.5'):continue
                raw=(folder/'index.faiss').read_bytes()
                if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:raise ValueError('Index integrity check failed.')
                import faiss
                index=faiss.read_index(str(folder/'index.faiss'))
                q=np.asarray(list(embedding_model(manifest['model']).query_embed(query)),dtype='float32');faiss.normalize_L2(q)
                sim,ix=index.search(q,min(30,index.ntotal))
                for rank,(score,j) in enumerate(zip(sim[0],ix[0]),1):
                    if j<0 or score<.25:continue
                    cid=manifest['chunks'][j]['id']
                    if cid in lookup:ranks[cid]=ranks.get(cid,0)+1/(60+rank)
                mode='Hybrid keyword + FAISS'
            except Exception as exc:notes.append('Semantic retrieval unavailable: '+str(exc)[:160])
    candidates=[dict(lookup[cid],retrieval_score=score) for cid,score in sorted(ranks.items(),key=lambda x:x[1],reverse=True)[:20]]
    if candidates and mode.startswith('Hybrid'):
        try:
            scores=list(reranker_model(os.getenv('RERANKER_MODEL','Xenova/ms-marco-MiniLM-L-6-v2')).rerank(query,[c['text'] for c in candidates]))
            for c,score in zip(candidates,scores):c['rerank_score']=float(score)
            candidates.sort(key=lambda c:c['rerank_score'],reverse=True);mode+=' + cross-encoder'
        except Exception as exc:notes.append('Reranking unavailable: '+str(exc)[:120])
    return candidates[:k],{'mode':mode,'notes':notes}
