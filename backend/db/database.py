from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

# Using SQLite with WAL mode (as per requirements)
# For local dev, we use a file-based DB. 
# check_same_thread=False is needed for SQLite with FastAPI (multiple threads)
sqlite_file_name = "openfeis.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(
    sqlite_url, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool # Simple pooling for SQLite
)

def create_db_and_tables():
    # Import all models to ensure they are registered with SQLModel.metadata
    # This must happen BEFORE create_all() is called
    from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry
    from backend.scoring_engine.models import Round, JudgeScore
    
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
