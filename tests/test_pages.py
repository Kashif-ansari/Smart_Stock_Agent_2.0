from streamlit.testing.v1 import AppTest
from src.core.config import ROOT

def assert_clean(app,page):
    assert not app.exception,(page,[x.message for x in app.exception])
    assert not app.error,(page,[x.value for x in app.error],[x.value for x in app.code])

def test_public_pages_and_demo_navigation():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run()
    assert_clean(app,'Home')
    for page in ['About us','Sign in','Home']:
        app.sidebar.radio[0].set_value(page).run();assert_clean(app,page)
    next(b for b in app.button if b.label=='Explore the demo').click().run()
    assert_clean(app,'Demo');assert app.sidebar.radio[0].value=='Dashboard'
    pages=list(app.sidebar.radio[0].options)
    for page in pages:
        app.sidebar.radio[0].set_value(page).run();assert_clean(app,page)
    app.sidebar.radio[0].set_value('Customer insights').run()
    next(b for b in app.button if b.label=='Evaluate churn model').click().run();assert_clean(app,'Churn')

def test_empty_workspace_and_restricted_navigation(owner,staff):
    from src.core.auth import login
    token=login('staff@example.test','Staff password 123')
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
    app.session_state['auth_token']=token;app.run()
    assert 'Finance' not in app.sidebar.radio[0].options
    assert 'HR & operations' not in app.sidebar.radio[0].options
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run();assert_clean(app,page)
