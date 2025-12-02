<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';

interface RankedResult {
  competitor_id: string;
  rank: number;
  irish_points: number;
  raw_score_sum: number;
}

interface RoundResult {
  round_id: string;
  results: RankedResult[];
}

// MVP: Hardcoded Round ID from store or selector
const currentRoundId = ref('r1');
const results = ref<RankedResult[]>([]);
const isLoading = ref(false);
const lastUpdated = ref<string | null>(null);

const fetchResults = async () => {
  isLoading.value = true;
  try {
    const response = await axios.get<RoundResult>(`http://localhost:8000/api/v1/results/${currentRoundId.value}`);
    results.value = response.data.results;
    lastUpdated.value = new Date().toLocaleTimeString();
  } catch (e) {
    console.error("Failed to fetch results", e);
  } finally {
    isLoading.value = false;
  }
};

// Auto-refresh every 5 seconds for "Real-time" feel
let intervalId: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  fetchResults();
  intervalId = setInterval(fetchResults, 5000);
});

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId);
  }
});
</script>

<template>
  <div class="p-6 bg-gray-50 min-h-screen">
    <header class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">Tabulation Dashboard</h1>
        <p class="text-gray-600">Round: {{ currentRoundId }}</p>
      </div>
      <div class="text-right">
        <p class="text-sm text-gray-500">Last Updated: {{ lastUpdated }}</p>
        <button 
          @click="fetchResults" 
          class="mt-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          :disabled="isLoading"
        >
          {{ isLoading ? 'Refreshing...' : 'Refresh Now' }}
        </button>
      </div>
    </header>

    <div class="bg-white shadow rounded-lg overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Competitor ID</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Irish Points</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="res in results" :key="res.competitor_id" :class="{'bg-yellow-50': res.rank === 1}">
            <td class="px-6 py-4 whitespace-nowrap">
              <span class="text-lg font-bold" :class="{'text-yellow-600': res.rank === 1}">
                {{ res.rank }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
              {{ res.competitor_id }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-right font-mono">
              {{ res.irish_points.toFixed(2) }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-right">
              <span v-if="res.rank <= 5" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                Recall
              </span>
              <span v-else class="text-gray-400">-</span>
            </td>
          </tr>
          <tr v-if="results.length === 0">
            <td colspan="4" class="px-6 py-8 text-center text-gray-500">
              No results calculated yet. Waiting for scores...
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

