import os
os.environ['SMARTSTOCK_TESTING']='true'
os.environ['DEBUG_ERRORS']='true'
os.environ['ENABLE_EXTERNAL_AI']='false'
os.environ['ENABLE_WEB_SEARCH']='false'
os.environ['ENABLE_MODEL_DOWNLOADS']='false'
os.environ['ENABLE_SEMANTIC_SEARCH']='false'
import pytest
from src.core.db import engine,init_db
from src.core.auth import register,context_from_token

@pytest.fixture(autouse=True)
def isolated_database(tmp_path,monkeypatch):
    if engine.cache_info().currsize:engine().dispose()
    engine.cache_clear()
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'test.db'))
    monkeypatch.setenv('STORAGE_PATH',str(tmp_path/'storage'))
    monkeypatch.setenv('ALLOW_SIGNUP','true')
    monkeypatch.setenv('ALLOW_DEMO','true')
    init_db()
    yield
    engine().dispose();engine.cache_clear()

@pytest.fixture
def owner():
    return context_from_token(register('Owner','owner@example.test','A long password 123','Test store'))

@pytest.fixture
def other():
    return context_from_token(register('Other','other@example.test','Another password 123','Other store'))

@pytest.fixture
def demo():
    from src.services.demo import create_demo
    token=create_demo()
    return context_from_token(token),token

@pytest.fixture
def staff(owner):
    from src.core.auth import invite
    token=invite(owner,'staff@example.test','inventory')
    return context_from_token(register('Staff','staff@example.test','Staff password 123','Store',token))
