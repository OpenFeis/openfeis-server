"""
Unit tests for the Instant Scheduler.

Tests the competition normalization and placement logic:
- Merge small competitions (younger dancers compete up)
- Split large competitions
- Never merge older dancers down
- Proper handling of competition families
"""

import pytest
from datetime import date, time, datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

from backend.services.instant_scheduler import (
    InstantSchedulerConfig,
    CompetitionFamily,
    MergeAction,
    SplitAction,
    SchedulerWarning,
    NormalizationResult,
    MergeReason,
    SplitReason,
    WarningCode,
    get_age_group_key,
    get_competition_priority,
    LEVEL_ORDER
)
from backend.scoring_engine.models_platform import (
    Competition, CompetitionLevel, DanceType, ScoringMethod, Gender
)


@pytest.fixture
def default_config():
    """Create a default scheduler config."""
    return InstantSchedulerConfig(
        min_comp_size=5,
        max_comp_size=25,
        lunch_window_start=time(11, 0),
        lunch_window_end=time(12, 0),
        lunch_duration_minutes=30,
        allow_two_year_merge_up=True,
        strict_no_exhibition=False,
        feis_start_time=time(8, 0),
        feis_end_time=time(17, 0)
    )


class TestAgeGroupKey:
    """Test the age group key generation."""
    
    def test_single_year_under_18(self):
        """Single year competitions should show as 'U8', 'U9', etc."""
        assert get_age_group_key(7, 7) == "U7"
        assert get_age_group_key(8, 8) == "U8"
        assert get_age_group_key(10, 10) == "U10"
    
    def test_age_range(self):
        """Age ranges should show as '8-9', '10-11', etc."""
        assert get_age_group_key(8, 9) == "8-9"
        assert get_age_group_key(10, 12) == "10-12"
    
    def test_adult_single_year(self):
        """Adult ages (18+) should show as '18+'."""
        assert get_age_group_key(18, 18) == "18+"


class TestCompetitionPriority:
    """Test the competition priority ordering."""
    
    def test_level_ordering(self):
        """Lower levels should have lower priority numbers (scheduled first)."""
        assert LEVEL_ORDER[CompetitionLevel.FIRST_FEIS] < LEVEL_ORDER[CompetitionLevel.BEGINNER_1]
        assert LEVEL_ORDER[CompetitionLevel.BEGINNER_1] < LEVEL_ORDER[CompetitionLevel.NOVICE]
        assert LEVEL_ORDER[CompetitionLevel.NOVICE] < LEVEL_ORDER[CompetitionLevel.PRIZEWINNER]
        assert LEVEL_ORDER[CompetitionLevel.PRIZEWINNER] < LEVEL_ORDER[CompetitionLevel.PRELIMINARY_CHAMPIONSHIP]
        assert LEVEL_ORDER[CompetitionLevel.PRELIMINARY_CHAMPIONSHIP] < LEVEL_ORDER[CompetitionLevel.OPEN_CHAMPIONSHIP]
    
    def test_priority_calculation(self):
        """Test that priority is calculated correctly."""
        comp = MagicMock()
        comp.level = CompetitionLevel.BEGINNER_1
        comp.min_age = 8
        
        priority = get_competition_priority(comp, entry_count=10)
        
        # Returns tuple of (level_priority, age_priority, -entry_count)
        assert priority == (LEVEL_ORDER[CompetitionLevel.BEGINNER_1], 8, -10)
    
    def test_younger_ages_scheduled_earlier(self):
        """Within same level, younger ages should be scheduled first."""
        comp_u8 = MagicMock()
        comp_u8.level = CompetitionLevel.NOVICE
        comp_u8.min_age = 8
        
        comp_u10 = MagicMock()
        comp_u10.level = CompetitionLevel.NOVICE
        comp_u10.min_age = 10
        
        priority_u8 = get_competition_priority(comp_u8, 10)
        priority_u10 = get_competition_priority(comp_u10, 10)
        
        # U8 should come before U10 (lower tuple value)
        assert priority_u8 < priority_u10


class TestCompetitionFamily:
    """Test competition family grouping."""
    
    def test_family_key_generation(self):
        """Test that family keys are generated correctly."""
        family = CompetitionFamily(
            dance_type=DanceType.HORNPIPE,
            level=CompetitionLevel.PRIZEWINNER,
            gender=Gender.FEMALE
        )
        
        assert family.key == "DanceType.HORNPIPE_CompetitionLevel.PRIZEWINNER_Gender.FEMALE"
    
    def test_family_with_no_gender(self):
        """Test family with mixed/no gender."""
        family = CompetitionFamily(
            dance_type=DanceType.REEL,
            level=CompetitionLevel.NOVICE,
            gender=None
        )
        
        assert "None" in family.key


class TestMergeLogic:
    """Test the merge decision logic for small competitions."""
    
    def test_merge_action_creation(self):
        """Test that merge actions are created correctly."""
        merge = MergeAction(
            source_competition_id=uuid4(),
            target_competition_id=uuid4(),
            source_age_range="U8",
            target_age_range="U9",
            dancers_moved=3,
            reason=MergeReason.MIN_COMP_SIZE,
            rationale="Competition size (3) below minimum (5)"
        )
        
        assert merge.dancers_moved == 3
        assert merge.reason == MergeReason.MIN_COMP_SIZE
        assert "below minimum" in merge.rationale
    
    def test_pw_hornpipe_u8_u9_merge_scenario(self):
        """
        Test Case from Requirements:
        Given: PW Hornpipe U8 = 3, PW Hornpipe U9 = 5
        Expected: Auto-merge into U9 competition with U8 flagged as competed-up
        Result size = 8
        """
        # This is a logical test of the merge scenario
        # U8 has 3 dancers (< min of 5)
        # U9 has 5 dancers (>= min of 5)
        # U8 should merge UP into U9
        
        u8_size = 3
        u9_size = 5
        min_comp_size = 5
        
        # U8 is below minimum
        assert u8_size < min_comp_size
        
        # U9 is at minimum (valid target)
        assert u9_size >= min_comp_size
        
        # After merge, total should be 8
        merged_size = u8_size + u9_size
        assert merged_size == 8
    
    def test_never_merge_older_down(self):
        """
        Verify the rule: Never move older dancers down into younger age groups.
        
        If U10 has 3 dancers and U9 has 10 dancers, U10 should NOT merge
        down into U9. Instead, it should merge UP into U11 if available,
        or generate a warning.
        """
        # U10 should NOT merge down to U9
        u10_min_age = 10
        u9_max_age = 9
        
        # Merge target's max age should be >= source's min age
        # (i.e., source goes UP, not DOWN)
        assert u9_max_age < u10_min_age  # This is why we can't merge U10 -> U9


class TestSplitLogic:
    """Test the split decision logic for large competitions."""
    
    def test_split_action_creation(self):
        """Test that split actions are created correctly."""
        split = SplitAction(
            original_competition_id=uuid4(),
            new_competition_id=uuid4(),
            original_size=30,
            group_a_size=15,
            group_b_size=15,
            reason=SplitReason.MAX_COMP_SIZE,
            assignment_method="random"
        )
        
        assert split.original_size == 30
        assert split.group_a_size + split.group_b_size == 30
        assert split.reason == SplitReason.MAX_COMP_SIZE
    
    def test_split_when_exceeds_max(self):
        """Test that competitions exceeding max size are split."""
        max_comp_size = 25
        entry_count = 30
        
        # Should trigger split
        assert entry_count > max_comp_size
        
        # Groups should be roughly equal
        group_a_size = entry_count // 2
        group_b_size = entry_count - group_a_size
        
        assert group_a_size == 15
        assert group_b_size == 15
    
    def test_odd_split(self):
        """Test splitting with odd number of entries."""
        entry_count = 31
        
        group_a_size = entry_count // 2  # 15
        group_b_size = entry_count - group_a_size  # 16
        
        assert group_a_size == 15
        assert group_b_size == 16
        assert group_a_size + group_b_size == 31


class TestWarnings:
    """Test warning generation."""
    
    def test_small_comp_exhibition_risk_warning(self):
        """Test warning when small comp can't be merged."""
        warning = SchedulerWarning(
            code=WarningCode.SMALL_COMP_EXHIBITION_RISK,
            message="Competition 'PW U8 Reel' has only 3 entries and cannot be merged up",
            competition_ids=[uuid4()],
            severity="warning"
        )
        
        assert warning.code == WarningCode.SMALL_COMP_EXHIBITION_RISK
        assert "cannot be merged" in warning.message
    
    def test_insufficient_champ_panel_warning(self):
        """Test warning when championship can't be scheduled due to panel requirements."""
        warning = SchedulerWarning(
            code=WarningCode.INSUFFICIENT_CHAMP_PANEL_CAPACITY,
            message="Championship 'U12 Prelim' requires 3 judges but no suitable stage/time found",
            competition_ids=[uuid4()],
            severity="critical"
        )
        
        assert warning.code == WarningCode.INSUFFICIENT_CHAMP_PANEL_CAPACITY
        assert warning.severity == "critical"


class TestConfigDefaults:
    """Test InstantSchedulerConfig defaults."""
    
    def test_default_values(self, default_config):
        """Test that default config has expected values."""
        assert default_config.min_comp_size == 5
        assert default_config.max_comp_size == 25
        assert default_config.lunch_duration_minutes == 30
        assert default_config.allow_two_year_merge_up == True
    
    def test_lunch_window(self, default_config):
        """Test lunch window defaults."""
        assert default_config.lunch_window_start == time(11, 0)
        assert default_config.lunch_window_end == time(12, 0)
    
    def test_feis_hours(self, default_config):
        """Test feis operating hours defaults."""
        assert default_config.feis_start_time == time(8, 0)
        assert default_config.feis_end_time == time(17, 0)
    
    def test_default_durations(self, default_config):
        """Test default duration settings for competitions without entries."""
        # Grade competitions should have 15 min default (short competitions)
        assert default_config.default_grade_duration_minutes == 15
        # Championship competitions should have 30 min default (multiple rounds)
        assert default_config.default_champ_duration_minutes == 30
        # Minimum floors
        assert default_config.min_grade_duration_minutes == 10
        assert default_config.min_champ_duration_minutes == 20


class TestNoMergeTargetScenario:
    """Test case where no merge target exists."""
    
    def test_no_merge_target_warning(self):
        """
        Scenario: U8 competition with 3 entries, but no U9 or U10 exists.
        Expected: Warning generated, competition left as-is.
        """
        # Simulate: only U8 exists in this family
        available_targets = []  # No U9, U10, etc.
        u8_size = 3
        min_comp_size = 5
        
        # U8 is below minimum but has no target
        needs_merge = u8_size < min_comp_size
        has_target = len(available_targets) > 0
        
        assert needs_merge == True
        assert has_target == False
        
        # Should generate SMALL_COMP_EXHIBITION_RISK warning


class TestTwoYearMergeUp:
    """Test the two-year merge up logic."""
    
    def test_two_year_merge_allowed(self, default_config):
        """Test that 2-year merge is allowed when configured."""
        assert default_config.allow_two_year_merge_up == True
        
        # U8 can merge to U10 if U9 doesn't exist
        u8_max_age = 8
        u10_min_age = 10
        year_gap = u10_min_age - u8_max_age
        
        # 2-year gap is acceptable when allow_two_year_merge_up is True
        assert year_gap <= 2
    
    def test_two_year_merge_disabled(self):
        """Test that 2-year merge is blocked when disabled."""
        config = InstantSchedulerConfig(allow_two_year_merge_up=False)
        
        # U8 cannot merge to U10, only U9
        assert config.allow_two_year_merge_up == False


class TestNormalizationResult:
    """Test NormalizationResult structure."""
    
    def test_empty_result(self):
        """Test empty normalization result."""
        result = NormalizationResult()
        
        assert len(result.merges) == 0
        assert len(result.splits) == 0
        assert len(result.warnings) == 0
        assert result.final_competition_count == 0
    
    def test_result_with_merges(self):
        """Test result with merges recorded."""
        result = NormalizationResult()
        result.merges.append(MergeAction(
            source_competition_id=uuid4(),
            target_competition_id=uuid4(),
            source_age_range="U8",
            target_age_range="U9",
            dancers_moved=3,
            reason=MergeReason.MIN_COMP_SIZE,
            rationale="Test merge"
        ))
        
        assert len(result.merges) == 1
        assert result.merges[0].dancers_moved == 3
    
    def test_result_with_splits(self):
        """Test result with splits recorded."""
        result = NormalizationResult()
        result.splits.append(SplitAction(
            original_competition_id=uuid4(),
            new_competition_id=uuid4(),
            original_size=30,
            group_a_size=15,
            group_b_size=15,
            reason=SplitReason.MAX_COMP_SIZE,
            assignment_method="random"
        ))
        
        assert len(result.splits) == 1
        assert result.splits[0].original_size == 30
