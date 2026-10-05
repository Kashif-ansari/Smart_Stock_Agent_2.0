import streamlit as st
from src.ui.components import header
from src.core.auth import allowed
from src.services.data import read_file,suggest_mapping,normalize,import_sales,datasets,ALIASES,safe_csv

def render(ctx):
    header('Your business records','Upload & data quality','Map your columns, inspect the quality report, and confirm what enters your business dataset.')
    if allowed(ctx,'sales.write'):
        f=st.file_uploader('Sales file',type=['csv','tsv','xlsx','xls'])
        st.download_button('Download CSV template',b'date,sku,quantity,product,price,unit_cost,category,customer_id,transaction_id\n2026-10-01,MILK-1,2,Milk 1L,290,231,Dairy,C001,T001\n',file_name='sales_template.csv')
        if f:
            raw=f.getvalue();frame,sheets=read_file(f.name,raw)
            if sheets:
                sheet=st.selectbox('Sheet',sheets);frame,_=read_file(f.name,raw,sheet)
            st.dataframe(frame.head(10),use_container_width=True,hide_index=True)
            st.subheader('Match your columns')
            suggested=suggest_mapping(frame);mapping={};cols=st.columns(3)
            for i,field in enumerate(ALIASES):
                options=['Not available']+list(frame.columns)
                default=options.index(suggested[field]) if suggested[field] in options else 0
                with cols[i%3]:value=st.selectbox(field.replace('_',' ').title()+(' *' if field in {'date','sku','quantity'} else ''),options,index=default,key='mapping_'+field)
                mapping[field]=None if value=='Not available' else value
            dayfirst=st.checkbox('Dates use day/month/year')
            zeros=st.checkbox('I confirm missing dates represent zero sales, not missing data or closures',value=False)
            if all(mapping.get(k) for k in ['date','sku','quantity']):
                clean,rejected,quality=normalize(frame,mapping,dayfirst)
                a,b,c=st.columns(3);a.metric('Accepted rows',quality['accepted_rows']);b.metric('Rejected rows',quality['rejected_rows']);c.metric('Valid rows',str(quality['score'])+'%')
                st.caption(quality['notes'][0])
                if quality['missing_price_rows']:st.warning('Some prices are missing. Revenue totals will be incomplete.')
                if not rejected.empty:
                    st.dataframe(rejected.head(25),hide_index=True)
                    st.download_button('Download rejected rows',safe_csv(rejected),file_name='rejected_rows.csv')
                st.download_button('Download corrected data',safe_csv(clean),file_name='validated_sales.csv')
                confirm=st.checkbox('I reviewed the mapping, dates, units and totals and approve importing accepted rows.')
                if st.button('Import accepted sales',type='primary',disabled=not confirm or clean.empty):
                    import_sales(ctx,f.name,raw,clean,quality,zeros);st.success('Dataset saved. Open Demand forecasting to create your first plan.')
    st.subheader('Dataset history')
    records=datasets(ctx)
    if records:st.dataframe([{'Dataset':d.name,'Rows':d.rows,'Valid rows %':d.quality.get('score'),'Imported':d.created_at,'ID':d.id} for d in records],hide_index=True,use_container_width=True)
    else:st.info('No datasets have been imported.')
