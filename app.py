import os
os.environ.setdefault('OTEL_SDK_DISABLED','true')
os.environ.setdefault('CREWAI_TRACING_ENABLED','false')
import streamlit as st
from importlib import import_module
from src.core.db import init_db
from src.core.auth import context_from_token,allowed,logout,tenant
from src.core.config import flag
from src.ui.components import styles

st.set_page_config(page_title='Smart Stock Agent',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
init_db();styles()

@st.cache_resource
def worker():
    from src.services.jobs import start_local_worker
    return start_local_worker()

if flag('AUTO_WORKER',True) and not flag('SMARTSTOCK_TESTING'):worker()

ctx=context_from_token(st.session_state.get('auth_token'))
from src.services.lifecycle import purge_revision
security_context=(ctx.user_id,ctx.tenant_id,ctx.role,purge_revision(ctx)) if ctx else None
if st.session_state.get('_security_context')!=security_context:
    keep={k:v for k,v in st.session_state.items() if k in {'auth_token','page','_next_page'}}
    st.session_state.clear();st.session_state.update(keep)
    st.session_state['_security_context']=security_context
if st.session_state.get('_next_page'):
    st.session_state['page']=st.session_state.pop('_next_page')
ROUTES={
 'Home':('home',None),'About us':('about',None),'Sign in':('login',None),
 'Dashboard':('dashboard','sales.read'),'Upload & data quality':('upload','sales.read'),
 'Demand forecasting':('forecast','sales.read'),'Inventory & reordering':('inventory','inventory.read'),
 'Business chatbot':('chatbot','chat'),'Knowledge base':('knowledge','knowledge.read'),
 'Customer insights':('customers','customers.read'),'Market opportunities':('market','market.read'),
 'Sales & pricing':('pricing','inventory.read'),'Finance':('finance','finance.read'),
 'HR & operations':('hr','hr.read'),'Reports & downloads':('reports','reports.read'),
 'Automation & approvals':('automation',None),'Settings':('settings',None)
}
with st.sidebar:
    st.markdown('<div class="brand"><span>◈</span> SMART STOCK <small>AGENT</small></div>',unsafe_allow_html=True)
    if ctx:
        business=tenant(ctx)
        st.caption('YOUR WORKSPACE')
        st.write('**'+business.name+'**')
        st.caption(ctx.name+' · '+ctx.role.title())
        if business.demo:st.info('Demo workspace · synthetic data')
        available=[x for x,(_,perm) in ROUTES.items() if x!='Sign in' and (perm is None or allowed(ctx,perm))]
    else:
        st.caption('Retail decisions, backed by evidence.')
        available=['Home','About us','Sign in']
    if st.session_state.get('page') not in available:st.session_state['page']='Dashboard' if ctx and 'Dashboard' in available else 'Home'
    current=st.radio('Navigate',available,key='page',label_visibility='collapsed')
    st.divider()
    if ctx and st.button('Sign out',use_container_width=True):
        logout(st.session_state['auth_token']);st.session_state.clear();st.rerun()
    st.caption('Plan • Review • Decide')

try:
    module,permission=ROUTES[current]
    if permission and not allowed(ctx,permission):raise PermissionError('This page is restricted.')
    if current in {'Automation & approvals','Settings'} and not ctx:raise PermissionError('Please sign in.')
    import_module('src.ui.pages.'+module).render(ctx)
except (ValueError,PermissionError) as exc:
    st.error(str(exc))
except Exception:
    st.error('This operation could not be completed. Review your input and server setup, then try again. No action is marked successful.')
    if flag('DEBUG_ERRORS'):
        import traceback
        st.code(traceback.format_exc())
