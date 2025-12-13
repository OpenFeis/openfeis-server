from typing import List, Dict, Tuple
from collections import defaultdict
import math
from .models import JudgeScore, RankedResult, RoundResult, JudgeScoreDetail

class IrishPointsCalculator:
    """
    Implements the Irish Points scoring logic per CLRG rules.
    """

    # Section 4.1: The Conversion Table
    # Explicit values from brief + standard increments
    POINTS_TABLE = {
        1: 100,
        2: 75,
        3: 65,
        4: 60,
        5: 56,
        6: 53,
        7: 50,
        8: 47,
        9: 45,
        10: 43,
        11: 40,
        12: 39,
        13: 38,
        14: 37,
        15: 36,
        16: 35,
        17: 34,
        18: 33,
        19: 32,
        20: 31,
        21: 30,
        22: 29,
        23: 28,
        24: 27,
        25: 26,
        26: 25,
        27: 24,
        28: 23,
        29: 22,
        30: 21,
        31: 20,
        32: 19,
        33: 18,
        34: 17,
        35: 16,
        36: 15,
        37: 14,
        38: 13,
        39: 12,
        40: 11,
        41: 10,
        42: 9,
        43: 8,
        44: 7,
        45: 6,
        46: 5,
        47: 4,
        48: 3,
        49: 2,
        50: 1
    }

    def get_irish_points_for_rank(self, rank: int) -> float:
        """
        Returns the Irish Points value for a given raw rank.
        Returns 0 for rank > 50.
        """
        return self.POINTS_TABLE.get(rank, 0.0)

    def calculate_round(self, round_id: str, scores: List[JudgeScore]) -> RoundResult:
        """
        Calculates the final placements and Irish Points for a round.
        CORRECTED LOGIC: Irish Points are calculated PER JUDGE, then summed.
        """
        # 1. Group scores by Judge
        # We need to process each judge's card individually first.
        judge_cards: Dict[str, List[JudgeScore]] = defaultdict(list)
        for score in scores:
            judge_cards[score.judge_id].append(score)

        # Dictionary to hold list of Irish Points for each competitor: {comp_id: [ip1, ip2, ...]}
        competitor_irish_points: Dict[str, List[float]] = defaultdict(list)
        
        # New: Dictionary to hold detailed scores: {comp_id: [JudgeScoreDetail, ...]}
        competitor_judge_details: Dict[str, List[JudgeScoreDetail]] = defaultdict(list)
        
        # 2. Convert Raw Scores to Irish Points for EACH Judge
        for judge_id, raw_scores in judge_cards.items():
            # Sort this judge's scores high to low (Raw Score)
            raw_scores.sort(key=lambda x: x.value, reverse=True)
            
            # Apply the "Split Points" logic to this specific judge's card
            i = 0
            current_rank = 1
            while i < len(raw_scores):
                # Check for ties within this judge's card
                tied_group = [raw_scores[i]]
                j = i + 1
                while j < len(raw_scores) and raw_scores[j].value == raw_scores[i].value:
                    tied_group.append(raw_scores[j])
                    j += 1
                
                num_tied = len(tied_group)
                
                # Calculate points for this rank position(s)
                points_sum = 0.0
                for k in range(num_tied):
                    points_sum += self.get_irish_points_for_rank(current_rank + k)
                
                # Round to 2 decimal places to avoid floating point equality issues
                avg_points = round(points_sum / num_tied, 2)
                
                # Award these points to the competitors
                for score in tied_group:
                    competitor_irish_points[score.competitor_id].append(avg_points)
                    
                    # Store detail
                    detail = JudgeScoreDetail(
                        judge_id=judge_id,
                        raw_score=score.value,
                        rank=current_rank, # or shared rank
                        irish_points=avg_points
                    )
                    competitor_judge_details[score.competitor_id].append(detail)
                
                current_rank += num_tied
                i += num_tied

        # 3. Sum Irish Points (Handle Drop High/Low on IP if applicable)
        final_results: List[RankedResult] = []

        for comp_id, ip_list in competitor_irish_points.items():
            total_ip = self._calculate_competitor_ip_total(ip_list)
            
            final_results.append(RankedResult(
                competitor_id=comp_id,
                irish_points=total_ip,
                rank=0, # Will be calculated next based on the IP totals
                raw_score_sum=0, # Raw sum is less relevant now, effectively 0 or N/A
                judge_scores=competitor_judge_details[comp_id]
            ))

        # 4. Final Ranking based on Total Irish Points
        final_results.sort(key=lambda x: x.irish_points, reverse=True)
        
        # Assign final 1st, 2nd, 3rd ranks based on the IP totals
        # We handle ties in the final rank display as well (shared rank, e.g., Joint 1st)
        # Note: Usually final results just display shared rank, they don't re-split points.
        
        current_rank = 1
        i = 0
        while i < len(final_results):
            tied_group = [final_results[i]]
            j = i + 1
            # Use math.isclose for safe float comparison
            while j < len(final_results) and math.isclose(final_results[j].irish_points, final_results[i].irish_points):
                tied_group.append(final_results[j])
                j += 1
            
            num_tied = len(tied_group)
            
            for res in tied_group:
                res.rank = current_rank
            
            # For display rank, we skip the next N ranks (e.g. 1, 1, 3...)
            current_rank += num_tied
            i += num_tied

        return RoundResult(round_id=round_id, results=final_results)

    def _calculate_competitor_ip_total(self, ip_scores: List[float]) -> float:
        """
        Calculates the sum of Irish Points, applying Drop High/Low if count is 5.
        """
        count = len(ip_scores)
        if count == 0:
            return 0.0
        
        if count == 5:
            # Drop highest and lowest IP
            sorted_scores = sorted(ip_scores)
            # Remove first (lowest) and last (highest)
            return round(sum(sorted_scores[1:-1]), 2)
        
        # Default: sum all
        return round(sum(ip_scores), 2)

    def calculate_recall(self, results: List[RankedResult]) -> List[str]:
        """
        Calculates the list of competitor IDs that recall to the final round (Round 3).
        
        Implements CLRG standard recall rules:
        
        1. **The Cutoff**: Strictly 50% of total competitors, rounded UP.
           - 10 dancers → 5 recalled
           - 11 dancers → 6 recalled (ceil(5.5) = 6)
           - 25 dancers → 13 recalled (ceil(12.5) = 13)
        
        2. **Tie Extension Rule**: If the dancer at the cutoff position is tied
           with dancers below them, ALL tied dancers must be recalled.
           We cannot eliminate a dancer on a tie.
           
           Example: Need to recall 5 dancers. 5th place has 150 points.
           6th and 7th place also have 150 points.
           Result: 7 dancers recalled (tie extends the cutoff).
        
        Args:
            results: List of RankedResult with competitor_id and irish_points.
                     Can be unsorted; method will sort by irish_points descending.
        
        Returns:
            List of competitor_id strings for dancers who recall.
        """
        if not results:
            return []

        # Sort by Irish Points (Descending)
        sorted_results = sorted(results, key=lambda x: x.irish_points, reverse=True)
        
        total_competitors = len(sorted_results)
        cutoff_index = math.ceil(total_competitors * 0.5)
        
        # Edge case: cutoff extends beyond list (everyone recalls)
        if cutoff_index >= total_competitors:
            return [r.competitor_id for r in sorted_results]
        
        # Get the score at the cutoff position
        cutoff_score = sorted_results[cutoff_index - 1].irish_points
        
        # Recall all dancers with score >= cutoff (handles tie extension)
        recalled_ids = []
        for r in sorted_results:
            if r.irish_points >= cutoff_score:
                recalled_ids.append(r.competitor_id)
            else:
                # Since list is sorted descending, we can break early
                break
                
        return recalled_ids
    
    # Alias for clarity in API usage
    calculate_recall_list = calculate_recall
