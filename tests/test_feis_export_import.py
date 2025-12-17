"""
Test feis export/import functionality.

This test verifies that:
1. A feis can be exported to JSON
2. The exported JSON contains all expected data
3. The JSON can be imported to create a new feis
4. The imported feis matches the original
"""
from datetime import date, datetime, time
from uuid import uuid4
from sqlmodel import Session, create_engine, SQLModel, select
from backend.scoring_engine.models_platform import (
    User, Feis, FeisSettings, Stage, Competition, Dancer, Entry,
    FeisAdjudicator, JudgePanel, PanelMember, StageJudgeCoverage,
    RoleType, CompetitionLevel, Gender, DanceType, CompetitionCategory,
    ScoringMethod, AdjudicatorStatus
)
from backend.services.feis_export import export_feis, import_feis
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_sample_feis(session: Session) -> tuple[Feis, User]:
    """Create a sample feis with all related data for testing."""
    # Create organizer
    organizer = User(
        email="organizer@test.com",
        name="Test Organizer",
        password_hash=pwd_context.hash("password123"),
        role=RoleType.ORGANIZER,
        email_verified=True
    )
    session.add(organizer)
    session.flush()
    
    # Create feis
    feis = Feis(
        name="Test Feis 2025",
        date=date(2025, 6, 15),
        location="Test Venue, Dublin",
        organizer_id=organizer.id
    )
    session.add(feis)
    session.flush()
    
    # Create settings
    settings = FeisSettings(
        feis_id=feis.id,
        base_entry_fee_cents=2500,
        per_competition_fee_cents=1000,
        family_max_cents=15000,
        late_fee_cents=500,
        registration_opens=datetime(2025, 3, 1, 9, 0),
        registration_closes=datetime(2025, 6, 1, 23, 59),
    )
    session.add(settings)
    
    # Create stages
    stage_a = Stage(
        feis_id=feis.id,
        name="Stage A",
        color="#FF5733",
        sequence=1
    )
    stage_b = Stage(
        feis_id=feis.id,
        name="Stage B",
        color="#33FF57",
        sequence=2
    )
    session.add_all([stage_a, stage_b])
    session.flush()
    
    # Create competitions
    comp1 = Competition(
        feis_id=feis.id,
        name="U8 Reel",
        min_age=6,
        max_age=7,
        level=CompetitionLevel.BEGINNER_1,
        gender=None,
        code="201R",
        category=CompetitionCategory.SOLO,
        dance_type=DanceType.REEL,
        tempo_bpm=113,
        bars=48,
        scoring_method=ScoringMethod.SOLO,
        stage_id=stage_a.id,
        scheduled_time=datetime(2025, 6, 15, 9, 0),
        estimated_duration_minutes=30
    )
    comp2 = Competition(
        feis_id=feis.id,
        name="U9 Light Jig",
        min_age=8,
        max_age=8,
        level=CompetitionLevel.NOVICE,
        gender=None,
        code="401LJ",
        category=CompetitionCategory.SOLO,
        dance_type=DanceType.LIGHT_JIG,
        tempo_bpm=115,
        bars=48,
        scoring_method=ScoringMethod.SOLO,
        stage_id=stage_a.id,
        scheduled_time=datetime(2025, 6, 15, 9, 30),
        estimated_duration_minutes=45
    )
    session.add_all([comp1, comp2])
    session.flush()
    
    # Create adjudicator
    adj = FeisAdjudicator(
        feis_id=feis.id,
        name="Judge Smith",
        email="judge@test.com",
        credential="TCRG",
        organization="CLRG",
        status=AdjudicatorStatus.CONFIRMED
    )
    session.add(adj)
    session.flush()
    
    # Create panel
    panel = JudgePanel(
        feis_id=feis.id,
        name="Championship Panel A",
        description="3-judge panel for championships"
    )
    session.add(panel)
    session.flush()
    
    panel_member = PanelMember(
        panel_id=panel.id,
        feis_adjudicator_id=adj.id,
        sequence=1
    )
    session.add(panel_member)
    
    # Create stage coverage
    coverage = StageJudgeCoverage(
        stage_id=stage_a.id,
        feis_adjudicator_id=adj.id,
        feis_day=date(2025, 6, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        note="Morning session"
    )
    session.add(coverage)
    
    # Create parent and dancer
    parent = User(
        email="parent@test.com",
        name="Test Parent",
        password_hash=pwd_context.hash("password123"),
        role=RoleType.PARENT,
        email_verified=True
    )
    session.add(parent)
    session.flush()
    
    dancer = Dancer(
        parent_id=parent.id,
        name="Test Dancer",
        dob=date(2018, 3, 15),
        current_level=CompetitionLevel.BEGINNER_1,
        gender=Gender.FEMALE
    )
    session.add(dancer)
    session.flush()
    
    # Create entries
    entry1 = Entry(
        dancer_id=dancer.id,
        competition_id=comp1.id,
        competitor_number=101,
        paid=True
    )
    entry2 = Entry(
        dancer_id=dancer.id,
        competition_id=comp2.id,
        competitor_number=102,
        paid=True
    )
    session.add_all([entry1, entry2])
    
    session.commit()
    
    return feis, organizer


def test_export_feis(session: Session):
    """Test that a feis can be exported to JSON."""
    feis, organizer = create_sample_feis(session)
    
    # Export the feis
    export_data = export_feis(session, feis.id)
    
    # Verify export structure
    assert export_data["export_version"] == "1.0"
    assert "exported_at" in export_data
    assert export_data["feis"]["name"] == "Test Feis 2025"
    assert export_data["feis"]["organizer_email"] == "organizer@test.com"
    
    # Verify settings
    assert export_data["settings"] is not None
    assert export_data["settings"]["base_entry_fee_cents"] == 2500
    
    # Verify stages
    assert len(export_data["stages"]) == 2
    assert export_data["stages"][0]["name"] == "Stage A"
    
    # Verify competitions
    assert len(export_data["competitions"]) == 2
    assert export_data["competitions"][0]["code"] == "201R"
    
    # Verify adjudicators
    assert len(export_data["adjudicators"]) == 1
    assert export_data["adjudicators"][0]["name"] == "Judge Smith"
    
    # Verify panels
    assert len(export_data["panels"]) == 1
    assert export_data["panels"][0]["name"] == "Championship Panel A"
    
    # Verify dancers
    assert len(export_data["dancers"]) == 1
    assert export_data["dancers"][0]["name"] == "Test Dancer"
    
    # Verify entries
    assert len(export_data["entries"]) == 2
    assert export_data["entries"][0]["competitor_number"] == 101


def test_import_feis(session: Session):
    """Test that an exported feis can be imported."""
    # Create and export a feis
    original_feis, original_organizer = create_sample_feis(session)
    export_data = export_feis(session, original_feis.id)
    
    # Create a new organizer for import
    import_organizer = User(
        email="importer@test.com",
        name="Import User",
        password_hash=pwd_context.hash("password123"),
        role=RoleType.ORGANIZER,
        email_verified=True
    )
    session.add(import_organizer)
    session.commit()
    
    # Import the feis
    report = import_feis(session, export_data, import_organizer, include_orders=True)
    
    # Verify import success
    assert report["success"] is True
    assert report["feis_name"] == "Test Feis 2025"
    
    # Verify created records
    assert report["created"]["stages"] == 2
    assert report["created"]["competitions"] == 2
    assert report["created"]["adjudicators"] == 1
    assert report["created"]["panels"] == 1
    assert report["created"]["entries"] == 2
    
    # Verify linked records (parent and dancer should be linked, not created)
    assert report["linked"]["users"] >= 1  # Parent should be linked
    assert report["linked"]["dancers"] >= 1  # Dancer should be linked
    
    # Verify the imported feis exists
    from uuid import UUID
    imported_feis = session.get(Feis, UUID(report["feis_id"]))
    assert imported_feis is not None
    assert imported_feis.name == "Test Feis 2025"
    assert imported_feis.organizer_id == import_organizer.id
    
    # Verify competitions were imported
    comps = session.exec(
        select(Competition).where(Competition.feis_id == imported_feis.id)
    ).all()
    assert len(comps) == 2
    
    # Verify stages were imported
    stages = session.exec(
        select(Stage).where(Stage.feis_id == imported_feis.id)
    ).all()
    assert len(stages) == 2


def test_import_with_existing_users(session: Session):
    """Test that import correctly links existing users instead of creating duplicates."""
    # Create original feis
    original_feis, original_organizer = create_sample_feis(session)
    export_data = export_feis(session, original_feis.id)
    
    # The parent and organizer already exist in the database
    # Import should link them, not create new ones
    
    # Count users before import
    users_before = len(session.exec(select(User)).all())
    
    # Import using the original organizer
    report = import_feis(session, export_data, original_organizer, include_orders=True)
    
    # Count users after import
    users_after = len(session.exec(select(User)).all())
    
    # Should have created minimal new users (only if adjudicator didn't have account)
    assert users_after <= users_before + 1  # At most 1 new user (judge without account)
    
    # Verify linked counts
    assert report["linked"]["users"] >= 1  # Parent should be linked
    assert report["linked"]["dancers"] >= 1  # Dancer should be linked


if __name__ == "__main__":
    # Run tests manually
    print("Testing export...")
    engine1 = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine1)
    with Session(engine1) as session:
        test_export_feis(session)
    print("✓ Export test passed")
    
    # Need fresh database for import test
    print("Testing import...")
    engine2 = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine2)
    with Session(engine2) as session:
        test_import_feis(session)
    print("✓ Import test passed")
    
    print("Testing import with existing users...")
    engine3 = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine3)
    with Session(engine3) as session:
        test_import_with_existing_users(session)
    print("✓ Import with existing users test passed")
    
    print("\n✓ All tests passed!")

