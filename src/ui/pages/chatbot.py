import pandas as pd
import streamlit as st
from src.ui.components import header,job_panel,report_actions
from src.services.jobs import queue

def render(ctx):
    header('Business assistant','Ask. Understand. Decide.','Get answers from your business records and approved documents, with the evidence kept in view.')
    mode=st.selectbox('Assistant mode',['Evidence only','Groq assistant','CrewAI review'])
    st.caption('Evidence only uses local calculations and retrieval. Live AI modes require configuration and workspace-owner consent.')
    prompts=['Which products should I reorder?','Summarize my sales revenue','What are my customer segments?','Explain the latest demand forecast']
    cols=st.columns(2)
    for i,p in enumerate(prompts):
        if cols[i%2].button(p,key='example_'+str(i),use_container_width=True):
            st.session_state.chat_question=p
            st.session_state.chat_job=queue(ctx,'chat',{'question':p,'mode':mode})
    question=st.chat_input('Ask about sales, stock, customers or a business policy')
    if question:
        st.session_state.chat_question=question
        st.session_state.chat_job=queue(ctx,'chat',{'question':question,'mode':mode})
    if st.session_state.get('chat_question'):
        with st.chat_message('user'):st.write(st.session_state.chat_question)
    result=job_panel(ctx,st.session_state.chat_job) if st.session_state.get('chat_job') else None
    if result:
        with st.chat_message('assistant'):
            st.markdown(result['answer'])
            for title,rows in result.get('tables',{}).items():
                st.write('**'+title+'**');st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            for note in result['notes']:st.caption(note)
        with st.expander('Sources and review trail',expanded=True):
            for citation in result['citations']:st.write(citation)
            st.dataframe(result['stages'],hide_index=True,use_container_width=True)
            st.caption(result['review']);st.caption(result['retrieval']['mode']+' · '+str(result['seconds'])+' seconds')
        report_actions(ctx,result['report'],'chat_report')

