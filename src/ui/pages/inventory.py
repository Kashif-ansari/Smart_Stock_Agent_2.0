import streamlit as st
from src.ui.components import header,empty,money,report_actions
from src.services.inventory import products,replenishment,update_product,propose
from src.services.reports import build_report
from src.core.auth import allowed

def render(ctx):
    header('Operations','Buy the right amount','Review stock coverage, supplier constraints and proposed orders against your available budget.')
    a,b=st.columns([2,1])
    with a:budget=st.number_input('Available purchase budget',min_value=0.0,value=100000.0,step=5000.0)
    with b:service=st.selectbox('Planning service level',[.90,.95,.975,.99],index=1,format_func=lambda x:f'{x*100:g}%')
    plan=replenishment(ctx,service,budget);items=products(ctx)
    if plan.empty:empty('No inventory plan yet','Upload sales and confirm current stock counts first.');return
    a,b,c=st.columns(3);a.metric('Products to review',str(int(plan.needs_review.sum())));b.metric('Proposed order value',money(plan.estimated_cost.sum(),ctx));c.metric('Remaining budget',money(budget-plan.estimated_cost.sum(),ctx))
    st.dataframe(plan[['sku','product','on_hand','on_order','days_cover','reorder_point','suggested_quantity','estimated_cost']],hide_index=True,use_container_width=True)
    st.caption('Safety stock assumes independent demand and lead-time uncertainty. EOQ is a reference; final quantities respect shelf life, pack sizes, minimums and the shared budget. Defaults such as a 7-day lead time are planning assumptions until you confirm supplier data. Quantities are withheld for unconfirmed missing sales dates. Confirm physical stock counts before buying.')
    from datetime import date,timedelta
    expiring=[{'SKU':p.sku,'Product':p.name,'On hand':p.on_hand,'Expiry':p.expiry_date} for p in items if p.expiry_date and p.expiry_date<=(date.today()+timedelta(days=7)).isoformat() and p.on_hand>0]
    if expiring:
        st.warning('Review these products for expiry within seven days. Separate expired items before selling.')
        st.dataframe(expiring,hide_index=True,use_container_width=True)
    if allowed(ctx,'inventory.write'):
        one,two=st.tabs(['Prepare a purchase','Maintain stock and supplier data'])
        with one:
            selected=st.selectbox('Product to order',items,format_func=lambda x:x.name,key='order_product')
            row=plan[plan.sku==selected.sku].iloc[0]
            with st.form('purchase_form'):
                quantity=st.number_input('Order quantity',min_value=0,step=selected.pack_size,value=int(row.suggested_quantity))
                st.write('Unit cost: '+money(selected.unit_cost,ctx)+' · Supplier: '+selected.supplier)
                submitted=st.form_submit_button('Send for approval',type='primary')
            if submitted:propose(ctx,'purchase','Purchase '+selected.name,{'sku':selected.sku,'quantity':quantity});st.success('Purchase proposal is awaiting approval. No supplier order has been sent.')
        with two:
            p=st.selectbox('Product record',items,format_func=lambda x:x.name,key='stock_product')
            with st.form('stock_form'):
                c1,c2,c3=st.columns(3)
                vals={}
                with c1:
                    vals['on_hand']=st.number_input('Confirmed on-hand stock',min_value=0.0,value=float(p.on_hand))
                    vals['reserved']=st.number_input('Reserved units',min_value=0.0,value=float(p.reserved))
                    vals['backorders']=st.number_input('Unreserved backorders',min_value=0.0,value=float(p.backorders))
                with c2:
                    vals['lead_days']=st.number_input('Lead time in days',min_value=1,value=p.lead_days)
                    vals['lead_std']=st.number_input('Lead-time standard deviation',min_value=0.0,value=p.lead_std)
                    vals['pack_size']=st.number_input('Pack size',min_value=1,value=p.pack_size)
                with c3:
                    vals['moq']=st.number_input('Minimum order',min_value=1,value=p.moq)
                    vals['unit_cost']=st.number_input('Unit cost',min_value=0.0,value=p.unit_cost)
                    vals['shelf_days']=st.number_input('Remaining shelf life in days',min_value=1,value=p.shelf_days)
                vals['supplier']=st.text_input('Supplier',p.supplier)
                saved=st.form_submit_button('Save confirmed information')
            if saved:update_product(ctx,p.sku,vals);st.success('Product information updated.');st.rerun()
    payload=build_report('Replenishment plan','Budget-constrained proposals for review.',{'Proposed replenishment':plan.where(plan.notna(),None).to_dict('records')},['Current catalog and accepted sales records'],['Current stock must be physically confirmed. No purchase is executed by this report.'],'inventory')
    report_actions(ctx,payload,'inventory_report')
