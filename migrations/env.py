from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine,pool
from src.core.config import database_url
from src.core.models import Base

config=context.config
if config.config_file_name:fileConfig(config.config_file_name)
target_metadata=Base.metadata

if context.is_offline_mode():
    context.configure(url=database_url(),target_metadata=target_metadata,literal_binds=True,dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():context.run_migrations()
else:
    connectable=create_engine(database_url(),poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata,compare_type=True,render_as_batch=connection.dialect.name=='sqlite')
        with context.begin_transaction():context.run_migrations()
