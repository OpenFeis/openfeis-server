import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { 
  CompetitionForScoring, 
  CompetitorForScoring, 
  ScoreSubmission 
} from '../models/types';
import { useAuthStore } from './auth';
import { useLocalResultsStore } from './localResults';
import { dbService } from '../services/db';
import { scoreSocket, type ScoreMessage } from '../services/scoreSocket';
import { v4 as uuidv4 } from 'uuid';

const API_URL = '/api/v1';

// Local score for offline storage
interface LocalScore {
  id: string;
  entry_id: string;
  competition_id: string;
  value: number;
  notes?: string;
  timestamp: string;
  synced: boolean;
}

export const useScoringStore = defineStore('scoring', () => {
  // State
  const competitions = ref<CompetitionForScoring[]>([]);
  const selectedCompetition = ref<CompetitionForScoring | null>(null);
  const competitors = ref<CompetitorForScoring[]>([]);
  const isOnline = ref(navigator.onLine);
  const isLoading = ref(false);
  const isSyncing = ref(false);
  const error = ref<string | null>(null);

  // Local results store reference
  const localResultsStore = useLocalResultsStore();

  // Listen for network status
  window.addEventListener('online', () => {
    isOnline.value = true;
    syncPendingScores();
    // Reconnect WebSocket
    if (selectedCompetition.value) {
      scoreSocket.connect(selectedCompetition.value.id);
    }
  });
  window.addEventListener('offline', () => {
    isOnline.value = false;
    // Auto-enable local mode when offline
    localResultsStore.enableLocalMode();
  });

  // WebSocket score handler - update local state when other judges submit
  // Note: unsubscribe function stored but not used - store lifetime matches app lifetime
  scoreSocket.onScore((scoreMsg: ScoreMessage) => {
    // If we're viewing this competition, we might want to update the UI
    // For now, just notify the local results store
    if (selectedCompetition.value?.id === scoreMsg.competition_id) {
      localResultsStore.onScoreReceived({
        id: uuidv4(),
        judge_id: scoreMsg.judge_id,
        competitor_id: scoreMsg.entry_id,
        round_id: scoreMsg.competition_id,
        value: scoreMsg.value,
        timestamp: scoreMsg.timestamp,
        synced: true,
      });
    }
  });

  // Get auth store for authenticated requests
  function getAuthFetch() {
    const auth = useAuthStore();
    return auth.authFetch;
  }

  // Fetch competitions available for scoring
  async function fetchCompetitions() {
    isLoading.value = true;
    error.value = null;
    
    try {
      const authFetch = getAuthFetch();
      const response = await authFetch(`${API_URL}/judge/competitions`);
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to fetch competitions');
      }
      
      competitions.value = await response.json();
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch competitions';
      competitions.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  // Select a competition and fetch its competitors
  async function selectCompetition(competition: CompetitionForScoring) {
    selectedCompetition.value = competition;
    
    // Register competition with local results store
    localResultsStore.registerCompetition({
      id: competition.id,
      name: competition.name,
      feis_id: competition.feis_id,
      feis_name: competition.feis_name,
    });
    
    // Connect/subscribe to WebSocket for real-time updates
    scoreSocket.connect(competition.id);
    
    await fetchCompetitors(competition.id);
  }

  // Clear competition selection
  function clearCompetition() {
    // Unsubscribe from WebSocket
    if (selectedCompetition.value) {
      scoreSocket.unsubscribeFromCompetition(selectedCompetition.value.id);
    }
    selectedCompetition.value = null;
    competitors.value = [];
  }

  // Fetch competitors for a competition
  async function fetchCompetitors(competitionId: string) {
    isLoading.value = true;
    error.value = null;
    
    try {
      const authFetch = getAuthFetch();
      const response = await authFetch(`${API_URL}/judge/competitions/${competitionId}/competitors`);
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to fetch competitors');
      }
      
      competitors.value = await response.json();
      
      // Register competitors with local results store for offline calculation
      localResultsStore.registerCompetitors(
        competitors.value.map(c => ({
          entry_id: c.entry_id,
          competitor_number: c.competitor_number,
          dancer_name: c.dancer_name,
          dancer_school: c.dancer_school ?? null,
        }))
      );
      
      // Merge any local unsynced scores
      await mergeLocalScores(competitionId);
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch competitors';
      competitors.value = [];
    } finally {
      isLoading.value = false;
    }
  }

  // Merge local unsynced scores with server data
  async function mergeLocalScores(competitionId: string) {
    try {
      const localScores = await dbService.getUnsyncedScores();
      const competitionScores = localScores.filter(
        (s: any) => s.competition_id === competitionId || s.round_id === competitionId
      );
      
      for (const localScore of competitionScores) {
        const competitor = competitors.value.find(
          c => c.entry_id === localScore.competitor_id
        );
        if (competitor && !competitor.existing_score) {
          competitor.existing_score = localScore.value;
          // Notes are stored separately in LocalScore format
        }
      }
    } catch (e) {
      console.warn('Could not merge local scores:', e);
    }
  }

  // Submit a score
  async function submitScore(
    entryId: string, 
    value: number, 
    notes?: string
  ): Promise<boolean> {
    if (!selectedCompetition.value) {
      error.value = 'No competition selected';
      return false;
    }

    const submission: ScoreSubmission = {
      entry_id: entryId,
      competition_id: selectedCompetition.value.id,
      value,
      notes
    };

    // Create local score for offline storage
    const localScore: LocalScore = {
      id: uuidv4(),
      entry_id: entryId,
      competition_id: selectedCompetition.value.id,
      value,
      notes,
      timestamp: new Date().toISOString(),
      synced: false
    };

    // Always save locally first (offline-first)
    try {
      await dbService.saveScore({
        id: localScore.id,
        judge_id: 'current', // Will be set by server
        competitor_id: entryId,
        round_id: selectedCompetition.value.id,
        value,
        timestamp: localScore.timestamp,
        synced: false
      });
    } catch (e) {
      console.warn('Could not save locally:', e);
    }

    // Update local state immediately
    const competitor = competitors.value.find(c => c.entry_id === entryId);
    if (competitor) {
      competitor.existing_score = value;
      competitor.existing_notes = notes;
    }

    // Try to sync with server
    if (isOnline.value) {
      try {
        const authFetch = getAuthFetch();
        const response = await authFetch(`${API_URL}/judge/scores`, {
          method: 'POST',
          body: JSON.stringify(submission)
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to submit score');
        }

        // Mark as synced
        await dbService.markSynced([localScore.id]);
        return true;
      } catch (e) {
        console.warn('Could not sync score, saved offline:', e);
        // Score is saved locally, will sync later
        return true;
      }
    }

    // Offline - score is saved locally
    return true;
  }

  // Sync pending scores when back online
  async function syncPendingScores() {
    if (isSyncing.value || !isOnline.value) return;

    isSyncing.value = true;
    
    try {
      const unsynced = await dbService.getUnsyncedScores();
      if (unsynced.length === 0) return;

      const authFetch = getAuthFetch();
      
      for (const score of unsynced) {
        try {
          const submission: ScoreSubmission = {
            entry_id: score.competitor_id,
            competition_id: score.round_id,
            value: score.value,
            notes: undefined // Local scores don't have notes in old format
          };

          const response = await authFetch(`${API_URL}/judge/scores`, {
            method: 'POST',
            body: JSON.stringify(submission)
          });

          if (response.ok) {
            await dbService.markSynced([score.id]);
          }
        } catch (e) {
          console.warn(`Could not sync score ${score.id}:`, e);
        }
      }

      console.log(`Synced ${unsynced.length} pending scores`);
    } catch (e) {
      console.error('Sync failed:', e);
    } finally {
      isSyncing.value = false;
    }
  }

  return {
    // State
    competitions,
    selectedCompetition,
    competitors,
    isOnline,
    isLoading,
    isSyncing,
    error,
    
    // Actions
    fetchCompetitions,
    selectCompetition,
    clearCompetition,
    fetchCompetitors,
    submitScore,
    syncPendingScores
  };
});
