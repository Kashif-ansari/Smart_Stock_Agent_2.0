"""Run as python -m scripts.check_setup; never prints secrets or database URLs."""
import importlib.util,sys,os
from pathlib import Path
from src.core.config import flag

def main():
    print('Python:',sys.version.split()[0])
    for name in ['streamlit','sqlalchemy','statsmodels','sklearn','faiss','groq','ddgs','crewai','fastembed','prophet','chronos','pytesseract']:
        print(f'{name}: '+('installed' if importlib.util.find_spec(name) else 'not installed'))
    print('Groq API key configured:',bool(os.getenv('GROQ_API_KEY')))
    for name in ['ENABLE_EXTERNAL_AI','ENABLE_WEB_SEARCH','ENABLE_SEMANTIC_SEARCH','ENABLE_MODEL_DOWNLOADS']:
        print(name+':',flag(name))
    from src.core.db import engine
    from sqlalchemy import text
    with engine().connect() as conn:conn.execute(text('SELECT 1'))
    print('Database connection: ready')
    print('Workspace consent is managed separately on Settings → Integrations.')

if __name__=='__main__':main()
