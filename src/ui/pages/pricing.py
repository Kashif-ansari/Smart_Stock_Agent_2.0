import streamlit as st
from src.ui.components import header,money
from src.services.inventory import products,propose
from src.core.auth import allowed

def render(ctx):
    header('Sales & pricing','Protect margin. Test your ideas.','Compare price scenarios with a margin floor. Approved changes update this app’s catalog; they do not change an external checkout system.')
    items=products(ctx)
    if not items:st.info('Upload products and confirm costs first.');return
    product=st.selectbox('Product',items,format_func=lambda p:p.name)
    a,b,c=st.columns(3);a.metric('Current price',money(product.price,ctx));b.metric('Unit cost',money(product.unit_cost,ctx));c.metric('Current gross margin',f'{(product.price-product.unit_cost)/product.price:.1%}' if product.price else 'Unavailable')
    with st.form('price_form'):
        floor=st.slider('Minimum gross margin',.05,.8,.2)
        price=st.number_input('Proposed price',min_value=0.01,value=max(.01,product.price),step=5.0)
        units=st.number_input('Scenario units',min_value=1,value=100)
        st.caption('Scenario units are a user assumption. This is not a measured price elasticity or a demand prediction.')
        submit=st.form_submit_button('Request price approval',disabled=not allowed(ctx,'inventory.write'))
    st.dataframe([{'Scenario':'Current','Price':product.price,'Revenue at assumed volume':product.price*units,'Gross profit at assumed volume':(product.price-product.unit_cost)*units},{'Scenario':'Proposed','Price':price,'Revenue at assumed volume':price*units,'Gross profit at assumed volume':(price-product.unit_cost)*units}],hide_index=True,use_container_width=True)
    if product.unit_cost<=0:st.warning('Confirm unit cost before relying on a margin calculation.')
    if submit:propose(ctx,'price','Price review '+product.name,{'sku':product.sku,'price':price,'margin_floor':floor});st.success('Price proposal sent for approval.')

