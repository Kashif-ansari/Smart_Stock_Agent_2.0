import streamlit as st
from src.ui.components import header,job_panel,report_actions
from src.services.jobs import queue
from src.services.market import history,set_status,assess_opportunity

def render(ctx):
    header('Market opportunities','Research before you restock','Explore public product evidence and use small, reviewable trials when considering a new product.')
    with st.form('research_form'):
        query=st.text_input('Public product or category query',placeholder='sugar free biscuits retail demand Pakistan')
        region=st.selectbox('Search region',['pk-en','us-en','uk-en','wt-wt'])
        st.caption('Do not include customer details, private supplier terms, account information or confidential business figures.')
        submit=st.form_submit_button('Research market',type='primary')
    if submit:st.session_state.market_job=queue(ctx,'research',{'query':query,'region':region})
    if st.session_state.get('market_job'):
        result=job_panel(ctx,st.session_state.market_job)
        if result:st.success('Research complete. Review source evidence below.')
    results=history(ctx)
    if not results:st.info('No market research yet. Enable public web research in Settings to get started.')
    with st.expander('Assess a new product pilot',expanded=not results):
        with st.form('market_pilot'):
            product=st.text_input('Full product name, brand, variant and pack size')
            a,b,c=st.columns(3)
            cost=a.number_input('Landed unit cost',min_value=0.0,value=100.0)
            price=b.number_input('Planned selling price',min_value=0.0,value=150.0)
            qty=c.number_input('Trial units (scenario)',min_value=1,value=12)
            a,b=st.columns(2)
            budget=a.number_input('Pilot cash budget',min_value=0.0,value=3000.0)
            shelf=b.number_input('Shelf life in days',min_value=1,value=90)
            available=st.checkbox('Supplier availability and landed cost have been checked')
            evidence=st.multiselect('Research supporting this pilot',results,format_func=lambda r:r.query)
            submit=st.form_submit_button('Check pilot')
        if submit:st.session_state.pilot_report=assess_opportunity(ctx,product,cost,price,qty,budget,available,shelf,[r.id for r in evidence])
        if st.session_state.get('pilot_report'):
            p=st.session_state.pilot_report;st.write(p['summary'])
            for title,rows in p['tables'].items():
                if rows:st.write(title);st.dataframe(rows,hide_index=True,use_container_width=True)
            report_actions(ctx,p,'pilot_report')
    for research in results[:10]:
        with st.expander(research.query+' · '+research.state,expanded=research==results[0]):
            for hit in research.payload:
                st.write('**'+hit['title']+'**');st.link_button('Read source',hit['url']);st.write(hit['snippet']);st.caption(hit['evidence_status']+' · '+hit['retrieved_at']);st.caption(hit['sales_claim'])
                if hit.get('source_text'):
                    with st.expander('Retrieved page extract'):st.text(hit['source_text'][:5000])
            st.warning('Search results do not prove local sales. Check supplier availability, landed cost, margin, shelf life and a pilot budget before buying.')
            status=st.selectbox('Recommendation status',['new','saved','dismissed','snoozed'],index=['new','saved','dismissed','snoozed'].index(research.state),key='marketstatus_'+research.id)
            if st.button('Update status',key='marketsave_'+research.id):set_status(ctx,research.id,status);st.rerun()
