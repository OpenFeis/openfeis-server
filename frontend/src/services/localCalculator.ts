/**
 * Local Irish Points Calculator
 * 
 * This is a TypeScript port of backend/scoring_engine/calculator.py
 * It enables offline tabulation when the server is unreachable.
 * 
 * IMPORTANT: This logic must stay in sync with the Python implementation!
 */

import type { JudgeScore } from '../models/types';

// ============= Types =============

export interface RankedResult {
  competitor_id: string;
  irish_points: number;
  rank: number;
  raw_score_sum: number;
}

export interface RoundResult {
  round_id: string;
  results: RankedResult[];
}

// ============= Points Table =============

/**
 * Section 4.1: The Conversion Table (CLRG Rules)
 * Explicit values for placements 1-50
 */
export const POINTS_TABLE: Record<number, number> = {
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
  50: 1,
};

// ============= Calculator Class =============

export class IrishPointsCalculator {
  /**
   * Returns the Irish Points value for a given raw rank.
   * Returns 0 for rank > 50.
   */
  getIrishPointsForRank(rank: number): number {
    return POINTS_TABLE[rank] ?? 0;
  }

  /**
   * Calculates the final placements and Irish Points for a round.
   * CORRECTED LOGIC: Irish Points are calculated PER JUDGE, then summed.
   */
  calculateRound(roundId: string, scores: JudgeScore[]): RoundResult {
    // 1. Group scores by Judge
    const judgeCards: Map<string, JudgeScore[]> = new Map();
    for (const score of scores) {
      const existing = judgeCards.get(score.judge_id) ?? [];
      existing.push(score);
      judgeCards.set(score.judge_id, existing);
    }

    // Dictionary to hold list of Irish Points for each competitor
    const competitorIrishPoints: Map<string, number[]> = new Map();

    // 2. Convert Raw Scores to Irish Points for EACH Judge
    for (const [_judgeId, rawScores] of judgeCards) {
      // Sort this judge's scores high to low (Raw Score)
      rawScores.sort((a, b) => b.value - a.value);

      // Apply the "Split Points" logic to this specific judge's card
      let i = 0;
      let currentRank = 1;

      while (i < rawScores.length) {
        // Check for ties within this judge's card
        const tiedGroup: JudgeScore[] = [rawScores[i]];
        let j = i + 1;

        while (j < rawScores.length && rawScores[j].value === rawScores[i].value) {
          tiedGroup.push(rawScores[j]);
          j++;
        }

        const numTied = tiedGroup.length;

        // Calculate points for this rank position(s)
        let pointsSum = 0;
        for (let k = 0; k < numTied; k++) {
          pointsSum += this.getIrishPointsForRank(currentRank + k);
        }

        // Round to 2 decimal places to avoid floating point equality issues
        const avgPoints = Math.round((pointsSum / numTied) * 100) / 100;

        // Award these points to the competitors
        for (const score of tiedGroup) {
          const existing = competitorIrishPoints.get(score.competitor_id) ?? [];
          existing.push(avgPoints);
          competitorIrishPoints.set(score.competitor_id, existing);
        }

        currentRank += numTied;
        i += numTied;
      }
    }

    // 3. Sum Irish Points (Handle Drop High/Low on IP if applicable)
    const finalResults: RankedResult[] = [];

    for (const [compId, ipList] of competitorIrishPoints) {
      const totalIp = this.calculateCompetitorIpTotal(ipList);

      finalResults.push({
        competitor_id: compId,
        irish_points: totalIp,
        rank: 0, // Will be calculated next based on IP totals
        raw_score_sum: 0, // Raw sum is less relevant now
      });
    }

    // 4. Final Ranking based on Total Irish Points
    finalResults.sort((a, b) => b.irish_points - a.irish_points);

    // Assign final ranks, handling ties
    let currentRank = 1;
    let i = 0;

    while (i < finalResults.length) {
      const tiedGroup: RankedResult[] = [finalResults[i]];
      let j = i + 1;

      // Use approximate comparison for floating point
      while (
        j < finalResults.length &&
        Math.abs(finalResults[j].irish_points - finalResults[i].irish_points) < 0.001
      ) {
        tiedGroup.push(finalResults[j]);
        j++;
      }

      const numTied = tiedGroup.length;

      for (const res of tiedGroup) {
        res.rank = currentRank;
      }

      // For display rank, we skip the next N ranks (e.g., 1, 1, 3...)
      currentRank += numTied;
      i += numTied;
    }

    return {
      round_id: roundId,
      results: finalResults,
    };
  }

  /**
   * Calculates the sum of Irish Points, applying Drop High/Low if count is 5.
   */
  private calculateCompetitorIpTotal(ipScores: number[]): number {
    const count = ipScores.length;
    if (count === 0) {
      return 0;
    }

    if (count === 5) {
      // Drop highest and lowest IP
      const sortedScores = [...ipScores].sort((a, b) => a - b);
      // Remove first (lowest) and last (highest)
      const middle = sortedScores.slice(1, -1);
      return Math.round(middle.reduce((a, b) => a + b, 0) * 100) / 100;
    }

    // Default: sum all
    return Math.round(ipScores.reduce((a, b) => a + b, 0) * 100) / 100;
  }

  /**
   * Calculates the list of competitor IDs that recall to the final round.
   * 
   * Implements CLRG standard recall rules:
   * 
   * 1. The Cutoff: Strictly 50% of total competitors, rounded UP.
   *    - 10 dancers → 5 recalled
   *    - 11 dancers → 6 recalled (ceil(5.5) = 6)
   *    - 25 dancers → 13 recalled (ceil(12.5) = 13)
   * 
   * 2. Tie Extension Rule: If the dancer at the cutoff position is tied
   *    with dancers below them, ALL tied dancers must be recalled.
   */
  calculateRecall(results: RankedResult[]): string[] {
    if (results.length === 0) {
      return [];
    }

    // Sort by Irish Points (Descending)
    const sortedResults = [...results].sort((a, b) => b.irish_points - a.irish_points);

    const totalCompetitors = sortedResults.length;
    const cutoffIndex = Math.ceil(totalCompetitors * 0.5);

    // Edge case: cutoff extends beyond list (everyone recalls)
    if (cutoffIndex >= totalCompetitors) {
      return sortedResults.map(r => r.competitor_id);
    }

    // Get the score at the cutoff position
    const cutoffScore = sortedResults[cutoffIndex - 1].irish_points;

    // Recall all dancers with score >= cutoff (handles tie extension)
    const recalledIds: string[] = [];
    for (const r of sortedResults) {
      if (r.irish_points >= cutoffScore) {
        recalledIds.push(r.competitor_id);
      } else {
        // Since list is sorted descending, we can break early
        break;
      }
    }

    return recalledIds;
  }
}

// Export singleton instance
export const localCalculator = new IrishPointsCalculator();

