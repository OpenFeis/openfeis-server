import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

# Using SQLite with WAL mode (as per requirements)
# For local dev, we use a file-based DB. 
# check_same_thread=False is needed for SQLite with FastAPI (multiple threads)
# In production, DB_PATH points to the persistent volume
sqlite_file_name = os.environ.get("DB_PATH", "openfeis.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(
    sqlite_url, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool # Simple pooling for SQLite
)


def run_migrations():
    """
    Simple migration helper for SQLite.
    Adds missing columns to existing tables.
    SQLite doesn't support full ALTER TABLE, but can add columns.
    """
    migrations = [
        # User table - email verification fields (added in v0.4.0)
        ("user", "email_verified", "ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"),
        ("user", "email_verification_token", "ALTER TABLE user ADD COLUMN email_verification_token VARCHAR"),
        ("user", "email_verification_sent_at", "ALTER TABLE user ADD COLUMN email_verification_sent_at DATETIME"),
        
        # Competition table - scheduling fields (added in Phase 2)
        ("competition", "dance_type", "ALTER TABLE competition ADD COLUMN dance_type VARCHAR"),
        ("competition", "tempo_bpm", "ALTER TABLE competition ADD COLUMN tempo_bpm INTEGER"),
        ("competition", "bars", "ALTER TABLE competition ADD COLUMN bars INTEGER DEFAULT 48"),
        ("competition", "scoring_method", "ALTER TABLE competition ADD COLUMN scoring_method VARCHAR DEFAULT 'SOLO'"),
        ("competition", "price_cents", "ALTER TABLE competition ADD COLUMN price_cents INTEGER DEFAULT 1000"),
        ("competition", "max_entries", "ALTER TABLE competition ADD COLUMN max_entries INTEGER"),
        ("competition", "stage_id", "ALTER TABLE competition ADD COLUMN stage_id VARCHAR"),
        ("competition", "scheduled_time", "ALTER TABLE competition ADD COLUMN scheduled_time DATETIME"),
        ("competition", "estimated_duration_minutes", "ALTER TABLE competition ADD COLUMN estimated_duration_minutes INTEGER"),
        ("competition", "adjudicator_id", "ALTER TABLE competition ADD COLUMN adjudicator_id VARCHAR"),
    ]
    
    with engine.connect() as conn:
        for table, column, sql in migrations:
            # Check if column exists
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]
            
            if column not in columns:
                print(f"Migration: Adding {table}.{column}")
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception as e:
                    print(f"Migration warning: {e}")
        
        # Data migration: Fix enum values (lowercase to uppercase)
        # This fixes the SQLAlchemy enum lookup issue
        try:
            conn.execute(text("UPDATE competition SET scoring_method = 'SOLO' WHERE scoring_method = 'solo'"))
            conn.execute(text("UPDATE competition SET scoring_method = 'CHAMPIONSHIP' WHERE scoring_method = 'championship'"))
            conn.execute(text("UPDATE competition SET dance_type = UPPER(dance_type) WHERE dance_type IS NOT NULL"))
            conn.commit()
            print("Migration: Fixed enum values to uppercase")
        except Exception as e:
            print(f"Migration warning (enum fix): {e}")


def create_db_and_tables():
    # Import all models to ensure they are registered with SQLModel.metadata
    # This must happen BEFORE create_all() is called
    from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry, SiteSettings, Stage
    from backend.scoring_engine.models import Round, JudgeScore
    
    SQLModel.metadata.create_all(engine)
    
    # Run migrations to add any missing columns to existing tables
    run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
