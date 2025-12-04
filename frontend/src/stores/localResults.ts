/**
 * Local Results Store
 * 
 * Manages competition results calculated locally from IndexedDB scores.
 * Used when in local/offline mode or when the API is unreachable.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { dbService } from '../services/db';
import { localCalculator } from '../services/localCalculator';
import type { JudgeScore } from '../models/types';

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

export interface LocalResultItem {
  rank: number;
  competitor_number: number | null;
  dancer_name: string;
  dancer_school: string | null;
  irish_points: number;
  is_recalled: boolean;
}

export interface LocalTabulatorResults {
  competition_id: string;
  competition_name: string;
  feis_name: string;
  total_competitors: number;
  total_scores: number;
  judge_count: number;
  results: LocalResultItem[];
  calculated_at: string;
}

// ============= Store =============

export const useLocalResultsStore = defineStore('localResults', () => {
  // State
  const isLocalMode = ref(false);
  const competitions = ref<LocalCompetition[]>([]);
  const competitors = ref<Map<string, LocalCompetitor>>(new Map());
  const currentResults = ref<LocalTabulatorResults | null>(null);
  const isCalculating = ref(false);
  const lastError = ref<string | null>(null);

  // Computed
  const hasLocalData = computed(() => competitions.value.length > 0);

  /**
   * Enable local mode (calculate results from IndexedDB)
   */
  function enableLocalMode() {
    isLocalMode.value = true;
    console.log('📴 Local mode enabled - calculating results from IndexedDB');
  }

  /**
   * Disable local mode (use API for results)
   */
  function disableLocalMode() {
    isLocalMode.value = false;
    currentResults.value = null;
    console.log('🌐 Online mode - using API for results');
  }

  /**
   * Toggle local mode
   */
  function toggleLocalMode() {
    if (isLocalMode.value) {
      disableLocalMode();
    } else {
      enableLocalMode();
    }
  }

  /**
   * Register a competition for local tracking.
   * Called when judges load competitions.
   */
  function registerCompetition(competition: LocalCompetition) {
    const existing = competitions.value.find(c => c.id === competition.id);
    if (!existing) {
      competitions.value.push(competition);
    }
  }

  /**
   * Register a competitor for local tracking.
   * Called when judges load competitors.
   */
  function registerCompetitor(competitor: LocalCompetitor) {
    competitors.value.set(competitor.entry_id, competitor);
  }

  /**
   * Register multiple competitors at once.
   */
  function registerCompetitors(competitorList: LocalCompetitor[]) {
    for (const competitor of competitorList) {
      registerCompetitor(competitor);
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

        resultItems.push({
          rank: ranked.rank,
          competitor_number: competitor?.competitor_number ?? null,
          dancer_name: competitor?.dancer_name ?? `Competitor ${ranked.competitor_id.slice(0, 8)}`,
          dancer_school: competitor?.dancer_school ?? null,
          irish_points: ranked.irish_points,
          is_recalled: recalledIds.has(ranked.competitor_id),
        });
      }

      // Sort by rank
      resultItems.sort((a, b) => a.rank - b.rank);

      const results: LocalTabulatorResults = {
        competition_id: competitionId,
        competition_name: competition?.name ?? 'Unknown Competition',
        feis_name: competition?.feis_name ?? 'Unknown Feis',
        total_competitors: resultItems.length,
        total_scores: allScores.length,
        judge_count: judgeIds.size,
        results: resultItems,
        calculated_at: new Date().toISOString(),
      };

      currentResults.value = results;
      return results;
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : 'Failed to calculate results';
      console.error('Local calculation failed:', error);
      return null;
    } finally {
      isCalculating.value = false;
    }
  }

  /**
   * Get all competitions that have local scores.
   */
  async function getCompetitionsWithLocalScores(): Promise<LocalCompetition[]> {
    try {
      const roundIds = new Set<string>();
      
      // Check which registered competitions have local scores
      for (const comp of competitions.value) {
        const scores = await dbService.getScoresForRound(comp.id);
        if (scores.length > 0) {
          roundIds.add(comp.id);
        }
      }

      return competitions.value.filter(c => roundIds.has(c.id));
    } catch (error) {
      console.error('Failed to get competitions with local scores:', error);
      return [];
    }
  }

  /**
   * Handle a new score being submitted (from WebSocket or local save).
   * Triggers recalculation if we're viewing that competition.
   */
  async function onScoreReceived(score: JudgeScore) {
    // If we're in local mode and viewing this competition, recalculate
    if (isLocalMode.value && currentResults.value?.competition_id === score.round_id) {
      await calculateResults(score.round_id);
    }
  }

  /**
   * Clear all local state (for testing or reset).
   */
  function reset() {
    isLocalMode.value = false;
    competitions.value = [];
    competitors.value.clear();
    currentResults.value = null;
    lastError.value = null;
  }

  return {
    // State
    isLocalMode,
    competitions,
    competitors,
    currentResults,
    isCalculating,
    lastError,

    // Computed
    hasLocalData,

    // Actions
    enableLocalMode,
    disableLocalMode,
    toggleLocalMode,
    registerCompetition,
    registerCompetitor,
    registerCompetitors,
    calculateResults,
    getCompetitionsWithLocalScores,
    onScoreReceived,
    reset,
  };
});

