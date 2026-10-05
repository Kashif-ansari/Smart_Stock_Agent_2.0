import streamlit as st
from src.ui.components import go

def render(ctx):
    st.markdown('<div class="eyebrow">Retail intelligence for everyday decisions</div>',unsafe_allow_html=True)
    st.markdown('''<div class="hero"><div class="eyebrow">SMART STOCK AGENT</div><h1>Know what to stock.<br><span class="highlight">Know when to act.</span></h1><p>Turn your sales history into a clear plan for demand, replenishment and growth. Review the evidence. Keep control of every decision.</p></div>''',unsafe_allow_html=True)
    a,b,c=st.columns([1.2,1.2,3])
    if ctx:
        if a.button('Open dashboard',type='primary',use_container_width=True):go('Dashboard')
        if b.button('Ask your assistant',use_container_width=True):go('Business chatbot')
    else:
        if a.button('Explore the demo',type='primary',use_container_width=True):
            from src.services.demo import create_demo
            with st.spinner('Preparing your private demo workspace...'):st.session_state.auth_token=create_demo()
            go('Dashboard')
        if b.button('Create your workspace',use_container_width=True):go('Sign in')
        st.caption('The demo uses synthetic records in a separate workspace. No API key is needed to explore core features.')
    st.write('')
    cards=[('01 / PLAN','Forecast with context','Compare demand patterns and see uncertainty before you commit your stock budget.'),('02 / DECIDE','Buy with confidence','Review reorder points, safety stock, pack sizes and cash limits in one place.'),('03 / UNDERSTAND','Ask the business assistant','Get calculations and source-backed answers from your own records and approved documents.')]
    for col,(num,title,body) in zip(st.columns(3),cards):
        with col:st.markdown(f'<div class="feature"><div class="num">{num}</div><h3>{title}</h3><p>{body}</p></div>',unsafe_allow_html=True)
    st.write('');st.subheader('From sales data to a reviewed decision')
    for col,(title,body) in zip(st.columns(4),[('Connect your records','Upload and validate sales files.'),('Find the signal','Forecast and analyze your business.'),('Review the recommendation','Inspect evidence and constraints.'),('Approve and follow through','Record the decision and measure results.')]):
        with col:st.markdown(f'<div class="step"><strong>{title}</strong><p>{body}</p></div>',unsafe_allow_html=True)

