<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useScoringStore } from '../../stores/scoring';
import type { Competitor } from '../../models/types';

const store = useScoringStore();

// Mock Competitors
const competitors = ref<Competitor[]>([
  { id: 'c1', number: '101', name: 'Saoirse Ronan' },
  { id: 'c2', number: '102', name: 'Cillian Murphy' },
  { id: 'c3', number: '103', name: 'Liam Neeson' },
  { id: 'c4', number: '104', name: 'Colin Farrell' },
]);

const selectedCompetitor = ref<string | null>(null);
const scoreInput = ref<number | null>(null);

onMounted(() => {
  store.loadScores();
});

const selectCompetitor = (id: string) => {
  selectedCompetitor.value = id;
  scoreInput.value = null; // Reset input
  
  // Check if already scored
  const existing = store.scores.find(s => s.competitor_id === id);
  if (existing) {
    scoreInput.value = existing.value;
  }
};

const saveScore = async () => {
  if (selectedCompetitor.value && scoreInput.value !== null) {
    await store.submitScore(selectedCompetitor.value, scoreInput.value);
    selectedCompetitor.value = null; // Return to list
  }
};

const getScoreDisplay = (compId: string) => {
  const score = store.scores.find(s => s.competitor_id === compId);
  return score ? score.value : '-';
};
</script>

<template>
  <div class="p-4 max-w-md mx-auto bg-white shadow rounded-lg">
    <header class="mb-4 flex justify-between items-center">
      <h1 class="text-xl font-bold">Judge Pad ({{ store.isOnline ? 'Online' : 'Offline' }})</h1>
      <span v-if="!store.isOnline" class="text-red-500 text-sm font-bold">⚠ Saving Locally</span>
    </header>

    <!-- Competitor List -->
    <div v-if="!selectedCompetitor">
      <h2 class="text-lg font-semibold mb-2">Round {{ store.currentRoundId }}</h2>
      <ul class="space-y-2">
        <li 
          v-for="comp in competitors" 
          :key="comp.id"
          @click="selectCompetitor(comp.id)"
          class="p-3 border rounded cursor-pointer hover:bg-gray-50 flex justify-between"
        >
          <span>#{{ comp.number }} - {{ comp.name }}</span>
          <span class="font-mono font-bold">{{ getScoreDisplay(comp.id) }}</span>
        </li>
      </ul>
    </div>

    <!-- Scoring Form -->
    <div v-else>
      <button @click="selectedCompetitor = null" class="mb-4 text-blue-600 underline">&larr; Back</button>
      <h2 class="text-lg font-bold mb-4">Score for #{{ competitors.find(c => c.id === selectedCompetitor)?.number }}</h2>
      
      <div class="flex gap-2 mb-4">
        <input 
          type="number" 
          v-model="scoreInput" 
          class="w-full p-3 border text-2xl text-center rounded" 
          placeholder="0-100"
        />
      </div>

      <button 
        @click="saveScore"
        class="w-full bg-green-600 text-white p-3 rounded font-bold text-lg"
      >
        Save Score
      </button>
    </div>
  </div>
</template>

