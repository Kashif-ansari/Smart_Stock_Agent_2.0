import streamlit as st
from src.ui.components import header
from src.services.analytics import employees,add_employee
from src.core.auth import allowed

def render(ctx):
    header('People & operations','Plan coverage with care','Keep staffing records restricted and review scheduling decisions with a responsible manager.')
    records=employees(ctx)
    a,b=st.columns(2);a.metric('Team members',len(records));b.metric('Available weekly hours',sum(e.weekly_hours for e in records))
    st.dataframe([{'Name':e.name,'Position':e.position,'Weekly hours':e.weekly_hours,'Availability':e.availability} for e in records],hide_index=True,use_container_width=True)
    if allowed(ctx,'hr.write'):
        with st.expander('Add a team member'):
            with st.form('employee'):
                name=st.text_input('Employee name');position=st.text_input('Position');hours=st.number_input('Available weekly hours',1,80,40);availability=st.text_input('Availability','Mon-Sat')
                submit=st.form_submit_button('Save staffing record')
            if submit:add_employee(ctx,name,position,hours,availability);st.rerun()
    required=st.number_input('Required store coverage hours per week',min_value=0,value=120)
    available=sum(e.weekly_hours for e in records)
    if available<required:st.warning(f'Coverage gap: {required-available} hours. Review availability and coverage requirements with the manager.')
    else:st.success('Aggregate hours cover the stated requirement. Confirm shift timing, breaks and individual availability before assigning work.')
    st.caption('This module supports records and coverage planning. It does not make hiring, dismissal, pay or disciplinary decisions.')

