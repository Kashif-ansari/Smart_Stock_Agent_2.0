from io import BytesIO
from pathlib import Path
from datetime import timedelta
import pandas as pd
import pytest
from sqlalchemy import select
from src.core.auth import *
from src.core.db import session
from src.core.models import Membership,Invite,Dataset,Job,Report,AgentRun,KnowledgeDoc
from src.services.data import read_file,normalize,suggest_mapping,import_sales,sales,datasets,delete_dataset
from src.services.reports import build_report,save_report,get_report,reports
from src.rag.retrieval import add_document,retrieve,delete_document
from src.services.jobs import queue,get_job,execute_job

def ingest(ctx):
    raw=b'order_date,item_code,qty,unit_price\n2026-01-01,SKU-1,2,100\n2026-01-02,SKU-1,-1,100\nwrong,SKU-1,3,100\n'
    frame,_=read_file('sales.csv',raw)
    clean,rejected,q=normalize(frame,suggest_mapping(frame))
    return import_sales(ctx,'sales.csv',raw,clean,q,True),raw,clean,rejected,q

def test_password_session_and_login_throttle(owner):
    h=password_hash('Correct password 123')
    assert password_ok('Correct password 123',h)
    assert not password_ok('wrong',h)
    token=login('owner@example.test','A long password 123')
    assert context_from_token(token).tenant_id==owner.tenant_id
    logout(token);assert context_from_token(token) is None
    for _ in range(5):
        with pytest.raises(ValueError):login('owner@example.test','wrong')
    with pytest.raises(ValueError,match='wait|attempt|Try again'):login('owner@example.test','A long password 123')

def test_role_revocation_is_live(owner,staff):
    assert allowed(staff,'inventory.write')
    assert not allowed(staff,'finance.read')
    with session() as s:
        s.scalar(select(Membership).where(Membership.user_id==staff.user_id)).active=False
    with pytest.raises(PermissionError):require(staff,'inventory.write')

def test_invite_expiry_and_role(owner):
    token=invite(owner,'new@example.test','finance')
    with session() as s:s.get(Invite,digest(token)).expires_at=now()-timedelta(seconds=1)
    with pytest.raises(ValueError,match='expired'):register('New','new@example.test','New password 123','Store',token)
    with pytest.raises(ValueError):invite(owner,'x@example.test','owner')

def test_mapping_returns_rejects_duplicates_and_isolation(owner,other):
    did,raw,clean,rejected,q=ingest(owner)
    assert (q['accepted_rows'],q['rejected_rows'],q['return_rows'])==(2,1,1)
    assert sales(owner).quantity.sum()==1
    assert sales(other,did).empty
    with pytest.raises(ValueError,match='already imported'):import_sales(owner,'again.csv',raw,clean,q)
    with pytest.raises(ValueError):delete_dataset(other,did)
    assert len(datasets(owner))==1

def test_upload_formats_and_safe_limits():
    f=pd.DataFrame({'date':['2026-01-01'],'sku':['SKU-1'],'quantity':[2]})
    b=BytesIO()
    with pd.ExcelWriter(b,engine='openpyxl') as w:f.to_excel(w,sheet_name='Sales',index=False);f.to_excel(w,sheet_name='Other',index=False)
    out,sheets=read_file('sales.xlsx',b.getvalue(),sheet='Sales')
    assert sheets==['Sales','Other'] and len(out)==1
    with pytest.raises(ValueError,match='Macro'):read_file('sales.xlsm',b.getvalue())
    with pytest.raises(ValueError):read_file('sales.exe',b'x')
    with pytest.raises(ValueError):read_file('sales.csv',b'x'*(11*1024**2))

def test_reports_and_retrieval_respect_domains(owner,staff,other):
    rid=save_report(owner,build_report('Private','HR confidential salary',scope='hr'))
    with pytest.raises(PermissionError):get_report(staff,rid)
    with pytest.raises(PermissionError):get_report(other,rid)
    assert reports(staff)==[]
    add_document(owner,'hr.txt',b'private salary inventory policy SECRET-432',scope='hr')
    add_document(owner,'stock.txt',b'inventory policy reorder milk SKU-1',scope='general')
    hits,_=retrieve(staff,'inventory SECRET-432')
    assert all(h['scope']=='general' for h in hits)
    assert retrieve(other,'inventory')[0]==[]
    from src.agents.pipeline import collect_evidence
    bundle=collect_evidence(owner,'inventory policy')
    assert 'SECRET-432' not in str(bundle)

def test_source_deletion_clears_derived_answers(owner):
    did,*_=ingest(owner)
    rid=save_report(owner,build_report('Sales','Private customer answer',scope='sales'))
    jid=queue(owner,'chat',{'question':'Summarize sales revenue','mode':'Evidence only'})
    execute_job(jid)
    assert get_job(owner,jid).state=='completed'
    path=Path(datasets(owner)[0].file_path)
    delete_dataset(owner,did)
    assert not path.exists() and sales(owner).empty and not reports(owner)
    assert get_job(owner,jid).result=={} and get_job(owner,jid).payload=={}
    with session() as s:assert not s.scalars(select(AgentRun)).all()

def test_knowledge_delete_removes_evidence(owner):
    did,_=add_document(owner,'policy.txt',b'Returns accepted within seven days.')
    assert retrieve(owner,'returns')[0]
    delete_document(owner,did)
    assert not retrieve(owner,'returns')[0]

def test_private_job_not_shared_or_reused(owner,staff):
    a=queue(owner,'chat',{'question':'general policy'})
    b=queue(staff,'chat',{'question':'general policy'})
    assert a!=b and get_job(staff,a) is None
