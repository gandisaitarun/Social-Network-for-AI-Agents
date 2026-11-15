from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _add_missing_agent_columns()


def _add_missing_agent_columns():
    # create_all() does not alter existing tables, so databases created before
    # agent API keys existed need the column added explicitly.
    columns = {column["name"] for column in inspect(engine).get_columns("agents")}
    if "api_key_hash" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE agents ADD COLUMN api_key_hash VARCHAR(64)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agents_api_key_hash ON agents (api_key_hash)"))
