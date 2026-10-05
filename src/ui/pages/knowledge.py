import streamlit as st
from src.ui.components import header,job_panel
from src.rag.retrieval import documents,permitted_scopes,add_document,delete_document,retrieve
from src.rag.extract import extract
from src.services.jobs import queue
from src.core.auth import allowed
from src.core.config import flag

def render(ctx):
    header('Business knowledge','Give your assistant the right context','Upload policies, supplier documents and product knowledge. Access permissions follow each collection.')
    if allowed(ctx,'knowledge.write'):
        a,b=st.columns([3,1])
        with a:f=st.file_uploader('Knowledge document',type=['pdf','docx','txt','md','csv','xlsx','xls','tsv','html','png','jpg','jpeg'])
        with b:scope=st.selectbox('Access collection',permitted_scopes(ctx))
        if f:
            try:
                pieces=extract(f.name,f.getvalue())
                with st.expander('Review extracted text before saving',expanded=True):
                    st.text('\n\n'.join(x['location']+'\n'+x['text'] for x in pieces)[:8000])
                confirmed=st.checkbox('I reviewed the extracted text and its access collection.')
                if st.button('Add to knowledge base',type='primary',disabled=not confirmed):
                    add_document(ctx,f.name,f.getvalue(),scope);st.success('Document saved. Keyword search is ready; rebuild the semantic index if enabled.')
            except ValueError as e:st.warning(str(e))
        if st.button('Build semantic index',disabled=not flag('ENABLE_SEMANTIC_SEARCH')):
            import uuid
            st.session_state.index_job=queue(ctx,'index',{'scope':scope},dedupe=str(uuid.uuid4()))
        if st.session_state.get('index_job'):
            result=job_panel(ctx,st.session_state.index_job)
            if result:st.success('Index ready: '+str(result['chunks'])+' chunks · '+result['model'])
    rows=documents(ctx)
    if rows:
        st.dataframe([{'Document':x.title,'Collection':x.scope,'Sections':len(x.payload),'Added':x.created_at} for x in rows],hide_index=True,use_container_width=True)
    else:st.info('Your knowledge base is empty.')
    with st.expander('Test retrieval'):
        query=st.text_input('Search your permitted documents')
        if query:
            hits,meta=retrieve(ctx,query);st.caption(meta['mode'])
            for hit in hits:st.write('**'+hit['title']+' · '+hit['location']+'**');st.write(hit['text'])
            if not hits:st.info('No supporting evidence found.')
            for note in meta['notes']:st.caption(note)
    if rows and allowed(ctx,'admin'):
        with st.expander('Remove a document'):
            item=st.selectbox('Document to remove',rows,format_func=lambda x:x.title)
            confirm=st.checkbox('Remove this document, its semantic index, all saved reports/answers and pending proposals; cancel current tasks.')
            if st.button('Delete document',disabled=not confirm):delete_document(ctx,item.id);st.rerun()
