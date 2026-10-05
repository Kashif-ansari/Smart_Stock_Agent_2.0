import pandas as pd
import plotly.express as px
import streamlit as st
from src.ui.components import header,empty
from src.services.data import sales
from src.analytics.customers import segment_customers,basket_rules,churn

def render(ctx):
    header('Customer intelligence','Understand who comes back','Explore purchase patterns, supported bundle ideas and measurable retention opportunities.')
    df=sales(ctx)
    if df.empty:empty('Customer data needed','Upload sales with stable customer IDs and transaction IDs.');return
    a,b,c=st.tabs(['RFM & segments','Market basket','Churn evaluation'])
    with a:
        result,metrics=segment_customers(df)
        if result.empty:st.info('No identifiable customer history. Individual segmentation is unavailable.')
        else:
            x,y,z=st.columns(3);x.metric('Identifiable customers',len(result));y.metric('At-risk customers',int(result.segment.isin(['At risk','Inactive']).sum()));z.metric('K-Means clusters',metrics.get('k','Not eligible'))
            counts=result.groupby('segment',as_index=False).size()
            fig=px.bar(counts,x='segment',y='size',color_discrete_sequence=['#0F766E']);fig.update_layout(height=270,xaxis_title=None,yaxis_title='Customers',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(result,hide_index=True,use_container_width=True)
            if metrics:st.caption('Silhouette score: '+str(metrics['silhouette'])+'. '+metrics['note'])
    with b:
        support=st.slider('Minimum support',.01,.30,.02)
        rules,n=basket_rules(df,support)
        st.caption(f'{n:,} eligible baskets · two-item association rules')
        if rules.empty:st.info('No rules meet the thresholds. Transaction-level product groups are required.')
        else:st.dataframe(rules.head(50),hide_index=True,use_container_width=True);st.caption('Association is not causation. Review margin and test bundles before rolling out.')
    with c:
        if st.button('Evaluate churn model'):
            with st.spinner('Evaluating chronological customer snapshots...'):st.session_state.churn_result=churn(df)
        result=st.session_state.get('churn_result')
        if result:
            if not result['available']:st.info(result['reason'])
            else:
                x,y,z=st.columns(3);x.metric('PR-AUC',f"{result['pr_auc']:.3f}");y.metric('Brier score',f"{result['brier']:.3f}");z.metric('Outcome prevalence',f"{result['baseline_prevalence']:.1%}")
                st.caption(result['note']);st.caption('Train cutoff '+result['train_cutoff']+' · Test cutoff '+result['test_cutoff'])
                st.dataframe(result['customers'],hide_index=True,use_container_width=True)
