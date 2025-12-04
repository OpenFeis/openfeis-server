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
        
        # Competition table - fee category (added in Phase 3)
        ("competition", "fee_category", "ALTER TABLE competition ADD COLUMN fee_category VARCHAR DEFAULT 'qualifying'"),
        
        # Competition table - display code (added in Phase 5)
        ("competition", "code", "ALTER TABLE competition ADD COLUMN code VARCHAR"),
        
        # Entry table - order_id (added in Phase 3)
        ("entry", "order_id", "ALTER TABLE entry ADD COLUMN order_id VARCHAR"),
        
        # Entry table - check-in fields (added in Phase 5)
        ("entry", "check_in_status", "ALTER TABLE entry ADD COLUMN check_in_status VARCHAR DEFAULT 'not_checked_in'"),
        ("entry", "checked_in_at", "ALTER TABLE entry ADD COLUMN checked_in_at DATETIME"),
        ("entry", "checked_in_by", "ALTER TABLE entry ADD COLUMN checked_in_by VARCHAR"),
        ("entry", "cancelled", "ALTER TABLE entry ADD COLUMN cancelled BOOLEAN DEFAULT 0"),
        ("entry", "cancelled_at", "ALTER TABLE entry ADD COLUMN cancelled_at DATETIME"),
        ("entry", "cancellation_reason", "ALTER TABLE entry ADD COLUMN cancellation_reason VARCHAR"),
        ("entry", "refund_amount_cents", "ALTER TABLE entry ADD COLUMN refund_amount_cents INTEGER DEFAULT 0"),
        
        # FeisSettings table - capacity & refund fields (added in Phase 5)
        ("feissettings", "global_dancer_cap", "ALTER TABLE feissettings ADD COLUMN global_dancer_cap INTEGER"),
        ("feissettings", "enable_waitlist", "ALTER TABLE feissettings ADD COLUMN enable_waitlist BOOLEAN DEFAULT 1"),
        ("feissettings", "waitlist_offer_hours", "ALTER TABLE feissettings ADD COLUMN waitlist_offer_hours INTEGER DEFAULT 48"),
        ("feissettings", "allow_scratches", "ALTER TABLE feissettings ADD COLUMN allow_scratches BOOLEAN DEFAULT 1"),
        ("feissettings", "scratch_refund_percent", "ALTER TABLE feissettings ADD COLUMN scratch_refund_percent INTEGER DEFAULT 50"),
        ("feissettings", "scratch_deadline", "ALTER TABLE feissettings ADD COLUMN scratch_deadline DATETIME"),
        
        # Order table - refund fields (added in Phase 5)
        # Note: "order" is a reserved SQL keyword, must be quoted
        ("order", "refund_total_cents", 'ALTER TABLE "order" ADD COLUMN refund_total_cents INTEGER DEFAULT 0'),
        ("order", "refunded_at", 'ALTER TABLE "order" ADD COLUMN refunded_at DATETIME'),
        ("order", "refund_reason", 'ALTER TABLE "order" ADD COLUMN refund_reason VARCHAR'),
        ("order", "stripe_refund_id", 'ALTER TABLE "order" ADD COLUMN stripe_refund_id VARCHAR'),
    ]
    
    with engine.connect() as conn:
        for table, column, sql in migrations:
            # Check if column exists
            # Quote the table name in case it's a reserved keyword (like "order")
            result = conn.execute(text(f'PRAGMA table_info("{table}")'))
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
    from backend.scoring_engine.models_platform import (
        User, Feis, Competition, Dancer, Entry, SiteSettings, Stage,
        FeisSettings, FeeItem, Order, OrderItem,  # Phase 3 models
        PlacementHistory, EntryFlag, AdvancementNotice,  # Phase 4 models
        WaitlistEntry, RefundLog  # Phase 5 models
    )
    from backend.scoring_engine.models import Round, JudgeScore
    
    SQLModel.metadata.create_all(engine)
    
    # Run migrations to add any missing columns to existing tables
    run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
