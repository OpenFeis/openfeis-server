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
        
        # Competition table - category and is_mixed (Enhanced Registration)
        ("competition", "category", "ALTER TABLE competition ADD COLUMN category VARCHAR DEFAULT 'SOLO'"),
        ("competition", "is_mixed", "ALTER TABLE competition ADD COLUMN is_mixed BOOLEAN DEFAULT 0"),
        
        # Dancer table - per-dance levels (Enhanced Registration)
        ("dancer", "level_reel", "ALTER TABLE dancer ADD COLUMN level_reel VARCHAR"),
        ("dancer", "level_light_jig", "ALTER TABLE dancer ADD COLUMN level_light_jig VARCHAR"),
        ("dancer", "level_slip_jig", "ALTER TABLE dancer ADD COLUMN level_slip_jig VARCHAR"),
        ("dancer", "level_single_jig", "ALTER TABLE dancer ADD COLUMN level_single_jig VARCHAR"),
        ("dancer", "level_treble_jig", "ALTER TABLE dancer ADD COLUMN level_treble_jig VARCHAR"),
        ("dancer", "level_hornpipe", "ALTER TABLE dancer ADD COLUMN level_hornpipe VARCHAR"),
        ("dancer", "level_traditional_set", "ALTER TABLE dancer ADD COLUMN level_traditional_set VARCHAR"),
        ("dancer", "level_figure", "ALTER TABLE dancer ADD COLUMN level_figure VARCHAR"),
        ("dancer", "is_adult", "ALTER TABLE dancer ADD COLUMN is_adult BOOLEAN DEFAULT 0"),
        
        # Competition table - Special competition fields (added in Special Competitions feature)
        ("competition", "description", "ALTER TABLE competition ADD COLUMN description VARCHAR"),
        ("competition", "allowed_levels", "ALTER TABLE competition ADD COLUMN allowed_levels VARCHAR"),
        
        # StageJudgeCoverage table - panel support (Judge Panel feature)
        ("stagejudgecoverage", "panel_id", "ALTER TABLE stagejudgecoverage ADD COLUMN panel_id VARCHAR"),
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
            # Fix category enum (Enhanced Registration)
            conn.execute(text("UPDATE competition SET category = 'SOLO' WHERE category = 'solo'"))
            conn.execute(text("UPDATE competition SET category = 'FIGURE' WHERE category = 'figure'"))
            conn.execute(text("UPDATE competition SET category = 'CHAMPIONSHIP' WHERE category = 'championship'"))
            conn.commit()
            print("Migration: Fixed enum values to uppercase")
        except Exception as e:
            print(f"Migration warning (enum fix): {e}")
        
        # Special migration: Make feis_adjudicator_id nullable for panel support
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        try:
            # Check current schema
            result = conn.execute(text("PRAGMA table_info('stagejudgecoverage')"))
            columns = {row[1]: row for row in result.fetchall()}
            
            if 'feis_adjudicator_id' in columns:
                # row[3] is the 'notnull' flag (1 = NOT NULL, 0 = nullable)
                is_not_null = columns['feis_adjudicator_id'][3] == 1
                
                if is_not_null:
                    print("Migration: Making stagejudgecoverage.feis_adjudicator_id nullable for panel support")
                    
                    # Recreate table with nullable feis_adjudicator_id
                    conn.execute(text("""
                        CREATE TABLE stagejudgecoverage_new (
                            id VARCHAR PRIMARY KEY,
                            stage_id VARCHAR NOT NULL,
                            feis_adjudicator_id VARCHAR,
                            panel_id VARCHAR,
                            feis_day DATE NOT NULL,
                            start_time TIME NOT NULL,
                            end_time TIME NOT NULL,
                            note VARCHAR,
                            created_at DATETIME NOT NULL,
                            FOREIGN KEY (stage_id) REFERENCES stage(id),
                            FOREIGN KEY (feis_adjudicator_id) REFERENCES feisadjudicator(id),
                            FOREIGN KEY (panel_id) REFERENCES judgepanel(id)
                        )
                    """))
                    
                    # Copy existing data
                    conn.execute(text("""
                        INSERT INTO stagejudgecoverage_new 
                        SELECT id, stage_id, feis_adjudicator_id, panel_id, feis_day, start_time, end_time, note, created_at
                        FROM stagejudgecoverage
                    """))
                    
                    # Drop old table
                    conn.execute(text("DROP TABLE stagejudgecoverage"))
                    
                    # Rename new table
                    conn.execute(text("ALTER TABLE stagejudgecoverage_new RENAME TO stagejudgecoverage"))
                    
                    conn.commit()
                    print("Migration: Successfully made feis_adjudicator_id nullable")
        except Exception as e:
            print(f"Migration warning (nullable feis_adjudicator_id): {e}")


def create_db_and_tables():
    # Import all models to ensure they are registered with SQLModel.metadata
    # This must happen BEFORE create_all() is called
    from backend.scoring_engine.models_platform import (
        User, Feis, Competition, Dancer, Entry, SiteSettings, Stage,
        FeisSettings, FeeItem, Order, OrderItem,  # Phase 3 models
        PlacementHistory, EntryFlag, AdvancementNotice,  # Phase 4 models
        WaitlistEntry, RefundLog,  # Phase 5 models
        FeisAdjudicator, AdjudicatorAvailability, StageJudgeCoverage,  # Phase 6 models
        FeisOrganizer,  # Phase 7 models
        JudgePanel, PanelMember  # Judge Panel feature
    )
    from backend.scoring_engine.models import Round, JudgeScore
    
    SQLModel.metadata.create_all(engine)
    
    # Run migrations to add any missing columns to existing tables
    run_migrations()


def get_session():
    with Session(engine) as session:
        yield session
