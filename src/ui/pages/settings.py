import os
from zoneinfo import ZoneInfo
import streamlit as st
from sqlalchemy import select,delete
from src.core.auth import allowed,require,tenant,invite,PERMISSIONS,audit
from src.core.db import session
from src.core.models import Tenant,Membership,User,Session,Audit
from src.core.config import flag
from src.services.data import datasets,delete_dataset
from src.ui.components import header

def render(ctx):
    header('Workspace settings','Your business. Your controls.','Manage access, operating preferences and permissions for external services.')
    t=tenant(ctx)
    if not allowed(ctx,'admin'):
        st.write('Workspace: '+t.name);st.write('Role: '+ctx.role);st.info('Contact your workspace owner to change access or external-service settings.');return
    a,b,c,d=st.tabs(['Business','Integrations','People & roles','Data & audit'])
    with a:
        st.caption('Currency is a reporting label; changing it does not convert historical amounts.')
        with st.form('business_settings'):
            name=st.text_input('Business name',t.name);currency=st.selectbox('Currency',['PKR','USD','EUR','GBP','AED'],index=['PKR','USD','EUR','GBP','AED'].index(t.currency) if t.currency in ['PKR','USD','EUR','GBP','AED'] else 0);tz=st.text_input('Business timezone',t.timezone)
            submitted=st.form_submit_button('Save business settings')
        if submitted:
            ZoneInfo(tz)
            with session() as s:
                row=s.get(Tenant,ctx.tenant_id);row.name=name[:120];row.currency=currency;row.timezone=tz;audit(s,ctx,'settings.updated',{'currency':currency,'timezone':tz})
            st.success('Settings saved.')
    with b:
        st.write('Enable only the external services your business has approved. Credentials belong in server environment variables, never chat messages or uploaded files.')
        st.dataframe([{'Integration':'Groq','Server ready':bool(os.getenv('GROQ_API_KEY')) and flag('ENABLE_EXTERNAL_AI')},{'Integration':'Public web search','Server ready':flag('ENABLE_WEB_SEARCH')},{'Integration':'Local semantic search','Server ready':flag('ENABLE_SEMANTIC_SEARCH')},{'Integration':'Model downloads','Server ready':flag('ENABLE_MODEL_DOWNLOADS')}],hide_index=True,use_container_width=True)
        with st.form('consent'):
            ai=st.checkbox('Allow minimized authorized business context to be sent to Groq',value=t.external_ai)
            web=st.checkbox('Allow public product/category web research',value=t.web_search)
            submitted=st.form_submit_button('Save service permissions')
        if submitted:
            with session() as s:
                row=s.get(Tenant,ctx.tenant_id);row.external_ai=ai;row.web_search=web;audit(s,ctx,'external.consent',{'ai':ai,'web':web})
            st.success('Workspace permissions saved. Server-level configuration is still required.')
        st.caption('Default embedding and reranking models are English. Urdu and Roman Urdu retrieval have not been validated; use approved English documents for the initial deployment.')
    with c:
        with session() as s:
            members=s.execute(select(Membership,User).join(User,Membership.user_id==User.id).where(Membership.tenant_id==ctx.tenant_id)).all()
        st.dataframe([{'Name':u.name,'Email':u.email,'Role':m.role,'Active':m.active} for m,u in members],hide_index=True,use_container_width=True)
        with st.form('invite'):
            email=st.text_input('Staff email');role=st.selectbox('Role',[r for r in PERMISSIONS if r!='owner']);submit=st.form_submit_button('Create invitation')
        if submit:st.code(invite(ctx,email,role));st.caption('Share this one-time code directly with the intended person. It expires after 48 hours. No message is sent automatically.')
        staff=[(m,u) for m,u in members if m.user_id!=ctx.user_id and m.role!='owner']
        if staff:
            selected=st.selectbox('Manage staff member',staff,format_func=lambda pair:pair[1].name)
            newrole=st.selectbox('Updated role',[r for r in PERMISSIONS if r!='owner']);active=st.checkbox('Access enabled',value=selected[0].active)
            if st.button('Update staff access'):
                with session() as s:
                    m=s.scalar(select(Membership).where(Membership.tenant_id==ctx.tenant_id,Membership.id==selected[0].id));m.role=newrole;m.active=active
                    s.execute(delete(Session).where(Session.tenant_id==ctx.tenant_id,Session.user_id==m.user_id));audit(s,ctx,'membership.updated',{'user_id':m.user_id,'role':newrole,'active':active})
                st.rerun()
    with d:
        records=datasets(ctx)
        if records:
            selected=st.selectbox('Dataset to delete',records,format_func=lambda x:x.name)
            st.warning('Deleting a source also removes all saved workspace reports and assistant answers, cancels tasks and pending proposals, and removes forecasts/schedules using this dataset. Catalog balances and completed business actions remain.')
            confirm=st.text_input('Type DELETE to confirm source and derived-data removal')
            if st.button('Delete dataset',disabled=confirm!='DELETE'):
                delete_dataset(ctx,selected.id)
                token=st.session_state.auth_token;st.session_state.clear();st.session_state.auth_token=token;st.rerun()
        with session() as s:logs=s.scalars(select(Audit).where(Audit.tenant_id==ctx.tenant_id).order_by(Audit.created_at.desc()).limit(100)).all()
        st.dataframe([{'Time':x.created_at,'Action':x.action,'Details':str(x.detail)} for x in logs],hide_index=True,use_container_width=True)
        st.caption('Backup expiry and storage encryption are deployment responsibilities. Deleting a source cannot recall files already downloaded by authorized users.')
