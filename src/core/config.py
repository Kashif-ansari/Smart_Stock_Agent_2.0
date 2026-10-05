from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env', override=False)

def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in {'1', 'true', 'yes'}

def storage():
    p = Path(os.getenv('STORAGE_PATH', str(ROOT / 'data')))
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p

def database_url():
    value = os.getenv('DATABASE_URL', 'sqlite:///data/smartstock.db')
    if value.startswith('sqlite:///') and not value.startswith('sqlite:////'):
        path = ROOT / value.removeprefix('sqlite:///')
        path.parent.mkdir(parents=True, exist_ok=True)
        return 'sqlite:///' + str(path)
    return value

def tenant_dir(tenant_id, category):
    import uuid
    uuid.UUID(tenant_id)
    if category not in {'uploads', 'knowledge', 'indexes', 'reports'}:
        raise ValueError('Invalid storage category')
    p = storage() / category / tenant_id
    p.mkdir(parents=True, exist_ok=True)
    return p

