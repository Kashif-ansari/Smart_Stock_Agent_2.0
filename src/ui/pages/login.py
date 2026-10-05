import os
import streamlit as st
from src.core.auth import register,login,oidc_login
from src.ui.components import header,go

def render(ctx):
    header('Your business workspace','Welcome to Smart Stock Agent','Sign in to manage your store, or create an isolated workspace for your business.')
    if os.getenv('AUTH_MODE','password')=='oidc':
        if st.user.is_logged_in:
            st.session_state.auth_token=oidc_login(dict(st.user));go('Dashboard')
        if st.button('Continue with your identity provider',type='primary'):st.login()
        return
    a,b=st.tabs(['Sign in','Create workspace or accept invite'])
    with a:
        with st.form('login_form'):
            email=st.text_input('Email');password=st.text_input('Password',type='password')
            submit=st.form_submit_button('Sign in',type='primary')
        if submit:
            st.session_state.auth_token=login(email,password);go('Dashboard')
    with b:
        with st.form('register_form'):
            name=st.text_input('Your name');business=st.text_input('Business name')
            email2=st.text_input('Your email');pw=st.text_input('Create a password',type='password',help='At least 12 characters.')
            invite=st.text_input('Invitation code',help='Leave blank to create your own workspace.')
            submit2=st.form_submit_button('Create account',type='primary')
        if submit2:
            st.session_state.auth_token=register(name,email2,pw,business,invite or None);go('Dashboard')

