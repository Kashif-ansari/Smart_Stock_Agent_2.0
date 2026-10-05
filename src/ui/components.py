from html import escape
import pandas as pd
import streamlit as st
from src.core.auth import allowed,tenant

def styles():
    st.markdown('''<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    html,body,[class*="css"],.stApp {font-family:'DM Sans',sans-serif;}
    h1,h2,h3 {font-family:Manrope,sans-serif;letter-spacing:-.035em;}
    .block-container {padding-top:2.25rem;padding-bottom:3rem;max-width:1450px;}
    [data-testid="stSidebar"] {background:#fff;border-right:1px solid #E2E8F0;}
    [data-testid="stSidebar"] .block-container {padding-top:1.5rem;}
    .brand {font:800 19px Manrope,sans-serif;letter-spacing:-.6px;color:#0F172A;margin:0 0 26px;}
    .brand span {color:#0F766E;font-size:30px;margin-right:6px;}
    .brand small {display:block;font-size:10px;letter-spacing:4px;margin-left:39px;line-height:5px;color:#64748B;}
    .eyebrow {color:#0F766E;font-size:11px;font-weight:800;letter-spacing:1.8px;text-transform:uppercase;margin-bottom:7px;}
    .page-title {font:800 34px Manrope,sans-serif;margin:0 0 8px;color:#0F172A;}
    .page-sub {color:#64748B;font-size:15px;max-width:820px;line-height:1.6;margin-bottom:25px;}
    .hero {background:#0F172A;border-radius:20px;padding:45px 44px;margin:12px 0 24px;position:relative;overflow:hidden;}
    .hero .eyebrow {color:#5EEAD4;}
    .hero h1 {font-size:52px;line-height:1.08;font-weight:800;color:white;max-width:750px;margin:15px 0;}
    .hero p {color:#CBD5E1;font-size:17px;max-width:610px;line-height:1.7;}
    .hero .highlight {color:#F59E0B;}
    .feature {background:white;border:1px solid #E2E8F0;border-radius:14px;padding:25px;min-height:192px;margin:8px 0;}
    .feature .num {font-weight:700;color:#0F766E;font-size:12px;letter-spacing:1px;margin-bottom:17px;}
    .feature h3 {font-size:19px;color:#0F172A;margin:0 0 10px;}
    .feature p {font-size:14px;color:#64748B;line-height:1.6;margin:0;}
    [data-testid="stMetric"] {background:#fff;border:1px solid #E2E8F0;border-radius:13px;padding:20px!important;}
    [data-testid="stMetricLabel"] {font-size:12px;color:#64748B;}
    [data-testid="stMetricValue"] {font-family:Manrope,sans-serif;font-weight:800;}
    .stButton>button {border-radius:9px;font-weight:600;min-height:41px;}
    .stTabs [data-baseweb="tab-list"] {gap:20px;}
    .stTabs [data-baseweb="tab"] {font-weight:600;}
    [data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
    .step {border-top:2px solid #0F766E;padding-top:14px;}
    .step strong {font-size:14px;}
    .step p {font-size:13px;color:#64748B;}
    @media(max-width:700px){.hero{padding:26px}.hero h1{font-size:35px}.page-title{font-size:28px}}
    </style>''',unsafe_allow_html=True)

def header(eyebrow,title,subtitle):
    st.markdown(f'<div class="eyebrow">{escape(eyebrow)}</div><h1 class="page-title">{escape(title)}</h1><p class="page-sub">{escape(subtitle)}</p>',unsafe_allow_html=True)

def empty(title,message):
    st.info('**'+title+'**\n\n'+message)

def money(value,ctx=None):
    currency=tenant(ctx).currency if ctx else 'PKR'
    if value is None:return 'Not available'
    return f'{currency} {value:,.0f}'

def go(page):
    st.session_state['_next_page']=page;st.rerun()

def report_actions(ctx,payload,key):
    from src.services.reports import save_report,export,scope_allowed
    if not scope_allowed(ctx,payload.get('scope','general')):return
    a,b=st.columns([1,3])
    with a:fmt=st.selectbox('Download format',['xlsx','pdf','docx','csv','txt','json'],key=key+'_format')
    with b:
        st.write('')
        st.download_button('Download report',export(payload,fmt),file_name='smart_stock_report.'+fmt,key=key+'_download',use_container_width=False)
    if allowed(ctx,'reports.write') and st.button('Save to reports',key=key+'_save'):
        save_report(ctx,payload);st.success('Report saved.')

def job_panel(ctx,jid):
    from src.services.jobs import get_job,cancel
    j=get_job(ctx,jid)
    if not j:return None
    if j.state=='completed':return j.result
    if j.state in {'failed','cancelled'}:st.warning(j.error or 'Job cancelled.');return None
    st.info('Your task is '+j.state+'. You can keep working while it runs.')
    a,b=st.columns(2)
    if a.button('Refresh status',key='refresh_'+jid):st.rerun()
    if b.button('Cancel task',key='cancel_'+jid):cancel(ctx,jid);st.rerun()
    return None
