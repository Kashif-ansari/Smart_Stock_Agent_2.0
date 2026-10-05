from datetime import datetime,date
import streamlit as st
from src.ui.components import header,money,report_actions
from src.services.analytics import finance,add_expense
from src.services.reports import build_report
from src.core.auth import allowed

def render(ctx):
    header('Finance','Keep the business affordable','Reconcile known sales, costs and expenses before committing more working capital.')
    values=finance(ctx)
    a,b,c,d=st.columns(4);a.metric('Recorded revenue',money(values['sales'],ctx));b.metric('Known product cost',money(values['known_cost'],ctx));c.metric('Gross profit estimate',money(values['gross_profit'],ctx));d.metric('Operating result estimate',money(values['operating_result'],ctx))
    st.caption(values.get('note','Upload sales to begin.'))
    if values['missing_cost_rows']:st.warning(str(values['missing_cost_rows'])+' rows have missing costs. Profit estimates are withheld.')
    rows=[{'date':e.date.date().isoformat(),'category':e.category,'amount':e.amount,'note':e.note} for e in values['expenses']]
    st.subheader('Recorded expenses')
    st.dataframe(rows,hide_index=True,use_container_width=True)
    if allowed(ctx,'finance.write'):
        with st.expander('Record an expense'):
            with st.form('expense'):
                dt=st.date_input('Expense date',date.today());category=st.selectbox('Category',['Rent','Utilities','Transport','Payroll','Supplies','Other']);amount=st.number_input('Amount',min_value=0.0,step=100.0);note=st.text_input('Description')
                submitted=st.form_submit_button('Save expense')
            if submitted:add_expense(ctx,datetime.combine(dt,datetime.min.time()),category,amount,note);st.rerun()
    summary=[{'measure':k,'value':values[k]} for k in ['sales','known_cost','gross_profit','missing_cost_rows','operating_result']]
    payload=build_report('Finance overview','Sales, known product costs and recorded expenses across the available records.',{'Summary':summary,'Expenses':rows},['Accepted sales records and recorded expenses'],['This estimate is not a cash ledger, tax filing or statutory accounting statement. Missing records can materially change the result.'],'finance')
    report_actions(ctx,payload,'finance_report')

