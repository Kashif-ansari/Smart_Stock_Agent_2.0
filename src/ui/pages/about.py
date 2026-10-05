import streamlit as st
from src.ui.components import header

def render(ctx):
    header('The project','A practical partner for retail teams','Smart Stock Agent brings demand planning, operations and business knowledge into one accountable workflow.')
    st.write('Our product goal is simple: help store owners make timely, informed buying and selling decisions. Recommendations show their evidence, limitations and approval state so the business stays in control.')
    st.subheader('Six people. One connected product.')
    roles=['Product lead & application integration','Data engineering & access controls','Forecasting & customer analytics','Knowledge systems & retrieval','Agent workflows & market research','Experience, reporting & quality']
    for start in range(0,6,3):
        for i,col in enumerate(st.columns(3),start):
            with col:
                with st.container(border=True):
                    st.markdown(f'### Member {i+1}')
                    st.write(roles[i]);st.caption('Profile details to be supplied by the project team.')
    st.info('Forecasts and recommendations are decision support. The business owner reviews purchases, price changes and sensitive actions.')

