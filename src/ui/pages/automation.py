import streamlit as st
from src.ui.components import header
from src.core.auth import allowed
from src.services.inventory import approvals,decide,execute
from src.services.jobs import jobs,schedules,schedule,toggle_schedule,queue
from src.services.data import datasets,sales
from src.agents.specs import SPECS

def render(ctx):
    header('Automation & approvals','Keep decisions accountable','Review proposed actions, monitor background tasks and control scheduled work.')
    a,b,c,d=st.tabs(['Approvals','Tasks','Schedules','Agent roles'])
    with a:
        if allowed(ctx,'approvals.read'):
            items=approvals(ctx)
            if not items:st.info('No proposals awaiting review.')
            for item in items[:30]:
                with st.expander(item.title+' · '+item.state,expanded=item.state=='pending'):
                    st.json(item.payload);st.caption('Decision deadline '+str(item.expires_at)+' UTC. Approved purchases remain on order until receipt.')
                    if item.state=='pending' and allowed(ctx,'approvals.decide'):
                        note=st.text_input('Decision note',key='note_'+item.id)
                        left,right=st.columns(2)
                        if left.button('Approve',key='yes_'+item.id):decide(ctx,item.id,True,note);st.rerun()
                        if right.button('Reject',key='no_'+item.id):decide(ctx,item.id,False,note);st.rerun()
                    if item.state=='approved' and item.kind in {'purchase','price'} and allowed(ctx,'inventory.write'):
                        label='Confirm goods received' if item.kind=='purchase' else 'Apply approved catalog price'
                        confirmed=st.checkbox('I confirm this action is accurate and ready to record.',key='confirmed_'+item.id)
                        if st.button(label,key='execute_'+item.id,disabled=not confirmed):execute(ctx,item.id);st.rerun()
        else:st.info('Your role does not include purchase approvals.')
    with b:
        items=jobs(ctx)
        st.dataframe([{'Task':j.kind,'Status':j.state,'Submitted':j.created_at,'Error':j.error,'ID':j.id} for j in items],hide_index=True,use_container_width=True)
        if st.button('Refresh tasks'):st.rerun()
        failed=[j for j in items if j.state=='failed']
        if failed:
            chosen=st.selectbox('Failed task',failed,format_func=lambda j:j.kind+' · '+j.error)
            if st.button('Submit a new attempt'):
                import uuid
                queue(ctx,chosen.kind,chosen.payload,dedupe=str(uuid.uuid4()));st.rerun()
    with c:
        if allowed(ctx,'jobs.manage'):
            records=schedules(ctx)
            for s in records:
                col1,col2=st.columns([3,1]);col1.write(s.kind+' · every '+str(s.interval_hours)+' hours · next '+str(s.next_run)+' UTC')
                if col2.button('Pause' if s.enabled else 'Resume',key='toggle_'+s.id):toggle_schedule(ctx,s.id,not s.enabled);st.rerun()
            st.subheader('Schedule a forecast')
            ds=datasets(ctx)
            if ds:
                selected=st.selectbox('Dataset to forecast',ds,format_func=lambda x:x.name)
                product=st.selectbox('Scheduled product',sorted(sales(ctx,selected.id).sku.unique()))
                interval=st.selectbox('Run every',[24,168,720],format_func=lambda x:f'{x} hours')
                if st.button('Create forecast schedule'):schedule(ctx,'forecast',{'dataset_id':selected.id,'sku':product,'horizon':14,'method':'Auto benchmark'},interval);st.rerun()
            st.caption('Schedules use elapsed intervals persisted in UTC. The Settings page records the store’s display timezone. Pause schedules when their source data is stale.')
        else:st.info('Schedule management is restricted to authorized managers.')
    with d:
        for spec in SPECS.values():
            with st.expander(spec['role']):
                for key,value in spec.items():
                    if key!='role':st.write('**'+key.replace('_',' ').title()+':** '+value)
