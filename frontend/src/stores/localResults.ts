/**
 * Local Results Store
 * 
 * Manages competition results calculated locally from IndexedDB scores.
 * Used when in local/offline mode or when the API is unreachable.
 */

import { defineStore } from 'pinia';
import { ref } from 'vue';
import { dbService } from '../services/db';
import { localCalculator } from '../services/localCalculator';

// ============= Types =============

export interface LocalCompetitor {
  entry_id: string;
  competitor_number: number | null;
  dancer_name: string;
  dancer_school: string | null;
}

export interface LocalCompetition {
  id: string;
  name: string;
  feis_id: string;
  feis_name: string;
}

export interface LocalJudgeScoreDetail {
  judge_id: string;
  judge_name: string | null;
  raw_score: number;
  rank: number;
  irish_points: number;
}

export interface LocalResultItem {
  rank: number;
  competitor_number: number | null;
  dancer_name: string;
  dancer_school: string | null;
  irish_points: number;
  is_recalled: boolean;
  judge_scores: LocalJudgeScoreDetail[];
}

export interface LocalTabulatorResults {
  competition_id: string;
  competition_name: string;
  feis_name: string;
  total_competitors: number;
  total_scores: number;
  judge_count: number;
  results: LocalResultItem[];
}

export interface LocalScoreUpdate {
  id: string;
  judge_id: string;
  competitor_id: string;
  round_id: string;
  value: number;
  timestamp: string;
  synced: boolean;
}

// ============= Store =============

export const useLocalResultsStore = defineStore('localResults', () => {
  // State
  const isLocalMode = ref(false);
  const competitions = ref<LocalCompetition[]>([]);
  const competitors = ref<Map<string, LocalCompetitor>>(new Map());
  const isCalculating = ref(false);
  const lastError = ref<string | null>(null);

  // Actions
  function toggleLocalMode() {
    isLocalMode.value = !isLocalMode.value;
  }

  function enableLocalMode() {
    isLocalMode.value = true;
  }

  function disableLocalMode() {
    isLocalMode.value = false;
  }

  /**
   * Register competition details for local lookup.
   * Called when loading competitions from API or local storage.
   */
  function registerCompetitions(compList: LocalCompetition[]) {
    competitions.value = compList;
  }

  /**
   * Register competitor details for local lookup.
   * Needed because scores only contain IDs.
   */
  function registerCompetitors(competitorList: LocalCompetitor[]) {
    for (const c of competitorList) {
      competitors.value.set(c.entry_id, c);
    }
  }

  /**
   * Handle incoming score (from WebSocket or Judge Pad).
   * Ensures the score is saved locally and invalidates cached results.
   */
  async function onScoreReceived(score: LocalScoreUpdate) {
    try {
      await dbService.saveScore({
        id: score.id,
        judge_id: score.judge_id,
        competitor_id: score.competitor_id,
        round_id: score.round_id,
        value: score.value,
        timestamp: score.timestamp,
        synced: score.synced
      });
    } catch (e) {
      console.warn('Failed to save received score locally:', e);
    }
  }

  /**
   * Calculate results for a competition using local IndexedDB scores.
   */
  async function calculateResults(competitionId: string): Promise<LocalTabulatorResults | null> {
    isCalculating.value = true;
    lastError.value = null;

    try {
      // Get all scores from IndexedDB for this round/competition
      const allScores = await dbService.getScoresForRound(competitionId);

      if (allScores.length === 0) {
        lastError.value = 'No scores found for this competition in local storage';
        return null;
      }

      // Get competition info
      const competition = competitions.value.find(c => c.id === competitionId);

      // Calculate results using the local calculator
      const roundResult = localCalculator.calculateRound(competitionId, allScores);

      // Calculate recall list
      const recalledIds = new Set(localCalculator.calculateRecall(roundResult.results));

      // Get unique judge count
      const judgeIds = new Set(allScores.map(s => s.judge_id));

      // Build result items with competitor info
      const resultItems: LocalResultItem[] = [];

      for (const ranked of roundResult.results) {
        const competitor = competitors.value.get(ranked.competitor_id);

        // Build detailed judge scores
        const judgeDetails: LocalJudgeScoreDetail[] = [];
        
        // Find raw scores for this competitor
        const compScores = allScores.filter(s => s.competitor_id === ranked.competitor_id);
        
        for (const score of compScores) {
            // Note: We don't have the per-judge rank/IP here easily without re-running logic
            // Ideally we should update localCalculator to return detail
            // For MVP local mode, we'll return basic data
            judgeDetails.push({
                judge_id: score.judge_id,
                judge_name: "Local Judge", // We might not have names locally
                raw_score: score.value,
                rank: 0, // Placeholder
                irish_points: 0 // Placeholder
            });
        }

        resultItems.push({
          rank: ranked.rank,
          competitor_number: competitor?.competitor_number ?? null,
          dancer_name: competitor?.dancer_name ?? `Competitor ${ranked.competitor_id.slice(0, 8)}`,
          dancer_school: competitor?.dancer_school ?? null,
          irish_points: ranked.irish_points,
          is_recalled: recalledIds.has(ranked.competitor_id),
          judge_scores: judgeDetails
        });
      }

      // Sort by rank
      resultItems.sort((a, b) => a.rank - b.rank);

      const results: LocalTabulatorResults = {
        competition_id: competitionId,
        competition_name: competition?.name || 'Unknown Competition',
        feis_name: competition?.feis_name || 'Local Feis',
        total_competitors: resultItems.length,
        total_scores: allScores.length,
        judge_count: judgeIds.size,
        results: resultItems,
      };

      return results;
    } catch (e) {
      console.error('Local calculation error:', e);
      lastError.value = e instanceof Error ? e.message : 'Unknown calculation error';
      return null;
    } finally {
      isCalculating.value = false;
    }
  }

  return {
    isLocalMode,
    competitions,
    isCalculating,
    lastError,
    toggleLocalMode,
    enableLocalMode,
    disableLocalMode,
    registerCompetitions,
    registerCompetitors,
    calculateResults,
    onScoreReceived
  };
});
