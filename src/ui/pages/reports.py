import streamlit as st
from src.ui.components import header,report_actions
from src.services.reports import reports,get_report

def render(ctx):
    header('Reports & downloads','Your decisions, documented','Open saved reports and export the same underlying figures in the format you need.')
    records=reports(ctx)
    if not records:st.info('Save a report from Forecasting, Inventory, Finance or the Business chatbot to see it here.');return
    chosen=st.selectbox('Saved report',records,format_func=lambda r:r.title+' · '+str(r.created_at))
    data=get_report(ctx,chosen.id)
    st.subheader(data['title']);st.write(data['summary']);st.caption(data['generated_at'])
    for title,rows in data['tables'].items():st.write('**'+title+'**');st.dataframe(rows,hide_index=True,use_container_width=True)
    with st.expander('Sources and limitations'):
        for x in data['sources']+data['limitations']:st.write(x)
    report_actions(ctx,data,'saved_report')

