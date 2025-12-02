"""
Unit tests for the Recall Calculator.

Tests the CLRG standard recall logic:
- 50% of competitors recalled (rounded up)
- Tie extension: dancers tied at cutoff are all recalled
"""

import pytest
from backend.scoring_engine.calculator import IrishPointsCalculator
from backend.scoring_engine.models import RankedResult


@pytest.fixture
def calculator():
    """Create a fresh calculator instance for each test."""
    return IrishPointsCalculator()


def make_result(competitor_id: str, irish_points: float, rank: int = 0) -> RankedResult:
    """Helper to create RankedResult objects for testing."""
    return RankedResult(
        competitor_id=competitor_id,
        irish_points=irish_points,
        rank=rank,
        raw_score_sum=0
    )


class TestRecallCalculator:
    """Test suite for calculate_recall method."""

    def test_clean_cut_10_dancers_top_5(self, calculator):
        """
        Scenario: Clean Cut
        10 dancers, top 5 are clearly separated from bottom 5.
        Expected: 5 IDs returned.
        """
        standings = [
            make_result("D1", 200),
            make_result("D2", 190),
            make_result("D3", 180),
            make_result("D4", 170),
            make_result("D5", 160),  # Cutoff line (5th place)
            make_result("D6", 150),  # Below cutoff
            make_result("D7", 140),
            make_result("D8", 130),
            make_result("D9", 120),
            make_result("D10", 110),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 5
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5"}

    def test_rounding_up_11_dancers(self, calculator):
        """
        Scenario: Rounding Up
        11 dancers: 50% = 5.5, rounded up = 6.
        Expected: 6 IDs returned.
        """
        standings = [
            make_result("D1", 200),
            make_result("D2", 190),
            make_result("D3", 180),
            make_result("D4", 170),
            make_result("D5", 160),
            make_result("D6", 150),  # Cutoff line (6th place, due to ceil)
            make_result("D7", 140),  # Below cutoff
            make_result("D8", 130),
            make_result("D9", 120),
            make_result("D10", 110),
            make_result("D11", 100),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 6
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5", "D6"}

    def test_tie_extension_at_cutoff(self, calculator):
        """
        Scenario: Tie Extension
        10 dancers. Top 4 are clear. 5th, 6th, and 7th place are all tied.
        The tie at 5th place extends to include 6th and 7th.
        Expected: 7 IDs returned.
        """
        standings = [
            make_result("D1", 200),   # 1st - clear
            make_result("D2", 190),   # 2nd - clear
            make_result("D3", 180),   # 3rd - clear
            make_result("D4", 170),   # 4th - clear
            make_result("D5", 160),   # 5th - TIED (cutoff line)
            make_result("D6", 160),   # 6th - TIED (same as 5th)
            make_result("D7", 160),   # 7th - TIED (same as 5th)
            make_result("D8", 150),   # Below cutoff
            make_result("D9", 140),
            make_result("D10", 130),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 7
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5", "D6", "D7"}
        # Verify D8-D10 are NOT recalled
        assert "D8" not in recalled
        assert "D9" not in recalled
        assert "D10" not in recalled

    def test_low_volume_3_dancers(self, calculator):
        """
        Scenario: Low Volume
        3 dancers: 50% = 1.5, rounded up = 2.
        Expected: 2 IDs returned.
        """
        standings = [
            make_result("D1", 200),
            make_result("D2", 150),  # Cutoff line
            make_result("D3", 100),  # Below cutoff
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 2
        assert set(recalled) == {"D1", "D2"}

    def test_empty_standings(self, calculator):
        """Edge case: Empty list should return empty list."""
        recalled = calculator.calculate_recall([])
        assert recalled == []

    def test_single_dancer(self, calculator):
        """
        Edge case: 1 dancer.
        50% = 0.5, rounded up = 1.
        Expected: 1 ID returned.
        """
        standings = [make_result("D1", 200)]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 1
        assert recalled == ["D1"]

    def test_two_dancers(self, calculator):
        """
        Edge case: 2 dancers.
        50% = 1, rounded up = 1.
        Expected: 1 ID returned.
        """
        standings = [
            make_result("D1", 200),
            make_result("D2", 150),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 1
        assert recalled == ["D1"]

    def test_all_tied(self, calculator):
        """
        Edge case: All dancers have the same score.
        Everyone at cutoff = everyone recalled.
        """
        standings = [
            make_result("D1", 150),
            make_result("D2", 150),
            make_result("D3", 150),
            make_result("D4", 150),
            make_result("D5", 150),
            make_result("D6", 150),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        # 50% of 6 = 3, but since all are tied at the cutoff, all 6 are recalled
        assert len(recalled) == 6
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5", "D6"}

    def test_unsorted_input(self, calculator):
        """
        The method should handle unsorted input correctly
        by sorting internally.
        """
        standings = [
            make_result("D5", 160),   # Will be 5th after sort
            make_result("D1", 200),   # Will be 1st after sort
            make_result("D3", 180),   # Will be 3rd after sort
            make_result("D10", 110),  # Will be 10th after sort
            make_result("D2", 190),   # Will be 2nd after sort
            make_result("D8", 130),
            make_result("D4", 170),
            make_result("D6", 150),
            make_result("D9", 120),
            make_result("D7", 140),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 5
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5"}

    def test_tie_at_top(self, calculator):
        """
        Edge case: Tie at the very top (joint 1st).
        Should not affect recall calculation.
        """
        standings = [
            make_result("D1", 200),   # Joint 1st
            make_result("D2", 200),   # Joint 1st
            make_result("D3", 180),
            make_result("D4", 170),
            make_result("D5", 160),   # Cutoff (5th entry = 50% of 10)
            make_result("D6", 150),
            make_result("D7", 140),
            make_result("D8", 130),
            make_result("D9", 120),
            make_result("D10", 110),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 5
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5"}

    def test_tie_extends_beyond_50_percent(self, calculator):
        """
        Edge case: Large tie at cutoff that extends well beyond 50%.
        8 dancers. 50% = 4. But 4th, 5th, 6th, 7th are all tied.
        Expected: 7 recalled (not 8, because 8th is below).
        """
        standings = [
            make_result("D1", 200),
            make_result("D2", 190),
            make_result("D3", 180),
            make_result("D4", 150),   # 4th - TIED (cutoff line)
            make_result("D5", 150),   # 5th - TIED
            make_result("D6", 150),   # 6th - TIED
            make_result("D7", 150),   # 7th - TIED
            make_result("D8", 100),   # 8th - Below cutoff (different score)
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 7
        assert set(recalled) == {"D1", "D2", "D3", "D4", "D5", "D6", "D7"}
        assert "D8" not in recalled

    def test_floating_point_scores(self, calculator):
        """
        Scores can be floating point (e.g., 82.5).
        Ensure ties are correctly detected with floats.
        """
        standings = [
            make_result("D1", 187.5),
            make_result("D2", 175.0),
            make_result("D3", 162.5),  # Cutoff (3rd of 6 = ceil(3) = 3)
            make_result("D4", 150.0),
            make_result("D5", 137.5),
            make_result("D6", 125.0),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 3
        assert set(recalled) == {"D1", "D2", "D3"}

    def test_floating_point_tie(self, calculator):
        """
        Tied scores with floating point values.
        """
        standings = [
            make_result("D1", 187.5),
            make_result("D2", 175.0),
            make_result("D3", 162.5),  # Cutoff - TIED
            make_result("D4", 162.5),  # TIED with D3
            make_result("D5", 137.5),
            make_result("D6", 125.0),
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 4
        assert set(recalled) == {"D1", "D2", "D3", "D4"}


class TestRecallEdgeCases:
    """Additional edge case tests."""

    def test_large_competition(self, calculator):
        """
        Stress test: 100 dancers with clean cut.
        50% = 50 recalled.
        """
        standings = [
            make_result(f"D{i}", 1000 - i * 10) 
            for i in range(1, 101)
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 50
        expected_ids = {f"D{i}" for i in range(1, 51)}
        assert set(recalled) == expected_ids

    def test_odd_number_25_dancers(self, calculator):
        """
        25 dancers: 50% = 12.5, rounded up = 13.
        """
        standings = [
            make_result(f"D{i}", 500 - i * 10) 
            for i in range(1, 26)
        ]
        
        recalled = calculator.calculate_recall(standings)
        
        assert len(recalled) == 13
        expected_ids = {f"D{i}" for i in range(1, 14)}
        assert set(recalled) == expected_ids

