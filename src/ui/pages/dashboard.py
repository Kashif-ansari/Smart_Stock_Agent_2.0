import pandas as pd
import plotly.express as px
import streamlit as st
from src.ui.components import header,empty,money
from src.services.data import sales
from src.services.inventory import replenishment
from src.core.auth import tenant

def render(ctx):
    business=tenant(ctx)
    header('Business overview','Your store, at a glance','Track selling activity, see what needs attention, and plan your next move.')
    df=sales(ctx)
    if df.empty:empty('Start with your sales data','Open Upload & data quality to import your first file.');return
    if df.price.isna().any():st.warning('Some unit prices are missing. Revenue charts include only rows with known prices.')
    end=df.date.max();current=df[df.date>end-pd.Timedelta(days=30)];previous=df[(df.date<=end-pd.Timedelta(days=30))&(df.date>end-pd.Timedelta(days=60))]
    revenue=float(current.revenue.sum());last=float(previous.revenue.sum());delta=f'{(revenue/last-1)*100:+.1f}% vs prior 30 days' if last else None
    plan=replenishment(ctx);low=int(plan.needs_review.sum()) if not plan.empty else 0
    c1,c2,c3,c4=st.columns(4)
    c1.metric('NET SALES · LAST 30 DAYS',money(revenue,ctx),delta)
    c2.metric('UNITS SOLD',f'{current.quantity.sum():,.0f}')
    c3.metric('PRODUCTS TO REVIEW',str(low))
    c4.metric('ACTIVE PRODUCTS',str(df.sku.nunique()))
    st.caption(f'Data through {end:%d %b %Y} · {len(df):,} imported rows · {business.currency}. Historical uploads do not automatically change current stock.')
    left,right=st.columns([1.8,1])
    with left:
        st.subheader('Sales performance')
        daily=df.groupby('date',as_index=False).revenue.sum().tail(90)
        fig=px.area(daily,x='date',y='revenue',color_discrete_sequence=['#0F766E'])
        fig.update_traces(line_width=2,fillcolor='rgba(15,118,110,.12)')
        fig.update_layout(height=300,margin=dict(l=0,r=0,t=10,b=0),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',xaxis_title=None,yaxis_title=business.currency)
        st.plotly_chart(fig,use_container_width=True)
    with right:
        st.subheader('Sales by category')
        categories=current.groupby('category',as_index=False).revenue.sum()
        fig=px.pie(categories,names='category',values='revenue',hole=.7,color_discrete_sequence=['#0F766E','#0F172A','#F59E0B','#99F6E4','#64748B','#CBD5E1'])
        fig.update_layout(height=300,margin=dict(l=0,r=0,t=10,b=0),legend=dict(orientation='h'),paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig,use_container_width=True)
    a,b=st.columns([1.35,1])
    with a:
        st.subheader('Replenishment priorities')
        if not plan.empty:st.dataframe(plan.loc[plan.needs_review,['product','on_hand','days_cover','suggested_quantity']].head(6),hide_index=True,use_container_width=True)
    with b:
        st.subheader('Top products')
        top=current.groupby('product',as_index=False).revenue.sum().sort_values('revenue',ascending=False).head(6)
        st.dataframe(top,hide_index=True,use_container_width=True)
