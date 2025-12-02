import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { JudgeScore } from '../models/types';
import { dbService } from '../services/db';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';

// Hardcoded for MVP
const API_URL = 'http://localhost:8000/api/v1';
const JUDGE_ID = 'judge-01'; // Mock Judge ID

export const useScoringStore = defineStore('scoring', () => {
  const currentRoundId = ref('r1');
  const scores = ref<JudgeScore[]>([]);
  const isOnline = ref(navigator.onLine);
  const isSyncing = ref(false);

  // Listen for network status
  window.addEventListener('online', () => {
    isOnline.value = true;
    syncScores();
  });
  window.addEventListener('offline', () => {
    isOnline.value = false;
  });

  async function loadScores() {
    scores.value = await dbService.getScoresForRound(currentRoundId.value);
  }

  async function submitScore(competitorId: string, value: number) {
    const newScore: JudgeScore = {
      id: uuidv4(),
      judge_id: JUDGE_ID,
      competitor_id: competitorId,
      round_id: currentRoundId.value,
      value: value,
      timestamp: new Date().toISOString(),
      synced: false,
    };

    // 1. Save Locally (Always succeeds)
    await dbService.saveScore(newScore);
    scores.value.push(newScore);

    // 2. Try to Sync (if online)
    if (isOnline.value) {
      try {
        await axios.post(`${API_URL}/scores`, newScore);
        await dbService.markSynced([newScore.id]);
      } catch (e) {
        console.warn("Sync failed, saved offline.", e);
      }
    }
  }

  async function syncScores() {
    if (isSyncing.value || !isOnline.value) return;
    
    const unsynced = await dbService.getUnsyncedScores();
    if (unsynced.length === 0) return;

    isSyncing.value = true;
    try {
      // Batch upload could be implemented here, sending one-by-one for MVP simplicity or use the batch endpoint
      await axios.post(`${API_URL}/scores/batch`, unsynced);
      
      const ids = unsynced.map(s => s.id);
      await dbService.markSynced(ids);
      console.log(`Synced ${ids.length} scores.`);
    } catch (e) {
      console.error("Batch sync failed", e);
    } finally {
      isSyncing.value = false;
    }
  }

  return {
    currentRoundId,
    scores,
    isOnline,
    submitScore,
    loadScores,
    syncScores
  };
});

