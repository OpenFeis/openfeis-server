<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';

interface FeisOption {
  id: string;
  name: string;
  date: string;
  location: string;
}

interface CompetitionWithScores {
  id: string;
  name: string;
  feis_id: string;
  feis_name: string;
  level: string;
  entry_count: number;
  score_count: number;
}

interface TabulatorResultItem {
  rank: number;
  competitor_number: number | null;
  dancer_name: string;
  dancer_school: string | null;
  irish_points: number;
  is_recalled: boolean;
}

interface TabulatorResults {
  competition_id: string;
  competition_name: string;
  feis_name: string;
  total_competitors: number;
  total_scores: number;
  judge_count: number;
  results: TabulatorResultItem[];
}

// State
const feiseanna = ref<FeisOption[]>([]);
const selectedFeisId = ref<string | null>(null);
const competitions = ref<CompetitionWithScores[]>([]);
const selectedCompetitionId = ref<string | null>(null);
const results = ref<TabulatorResults | null>(null);
const isLoadingFeiseanna = ref(false);
const isLoadingCompetitions = ref(false);
const isLoadingResults = ref(false);
const lastUpdated = ref<string | null>(null);
const autoRefresh = ref(true);

// Computed
const filteredCompetitions = computed(() => {
  if (!selectedFeisId.value) return competitions.value;
  return competitions.value.filter(c => c.feis_id === selectedFeisId.value);
});

// Fetch feiseanna
const fetchFeiseanna = async () => {
  isLoadingFeiseanna.value = true;
  try {
    const response = await fetch('/api/v1/feis');
    if (response.ok) {
      feiseanna.value = await response.json();
    }
  } catch (e) {
    console.error("Failed to fetch feiseanna", e);
  } finally {
    isLoadingFeiseanna.value = false;
  }
};

// Fetch competitions with scores
const fetchCompetitions = async () => {
  isLoadingCompetitions.value = true;
  try {
    const url = selectedFeisId.value 
      ? `/api/v1/tabulator/competitions?feis_id=${selectedFeisId.value}`
      : '/api/v1/tabulator/competitions';
    const response = await fetch(url);
    if (response.ok) {
      competitions.value = await response.json();
      // Auto-select first competition if only one exists
      if (competitions.value.length === 1 && competitions.value[0]) {
        selectedCompetitionId.value = competitions.value[0].id;
      }
    }
  } catch (e) {
    console.error("Failed to fetch competitions", e);
  } finally {
    isLoadingCompetitions.value = false;
  }
};

// Fetch results for selected competition
const fetchResults = async () => {
  if (!selectedCompetitionId.value) {
    results.value = null;
    return;
  }
  
  isLoadingResults.value = true;
  try {
    const response = await fetch(`/api/v1/competitions/${selectedCompetitionId.value}/results`);
    if (response.ok) {
      results.value = await response.json();
      lastUpdated.value = new Date().toLocaleTimeString();
    }
  } catch (e) {
    console.error("Failed to fetch results", e);
  } finally {
    isLoadingResults.value = false;
  }
};

// Watch for feis selection changes
watch(selectedFeisId, () => {
  selectedCompetitionId.value = null;
  results.value = null;
  fetchCompetitions();
});

// Watch for competition selection changes
watch(selectedCompetitionId, () => {
  if (selectedCompetitionId.value) {
    fetchResults();
  } else {
    results.value = null;
  }
});

// Auto-refresh every 5 seconds
let intervalId: ReturnType<typeof setInterval> | null = null;

const startAutoRefresh = () => {
  if (intervalId) clearInterval(intervalId);
  intervalId = setInterval(() => {
    if (autoRefresh.value && selectedCompetitionId.value) {
      fetchResults();
    }
  }, 5000);
};

onMounted(() => {
  fetchFeiseanna();
  fetchCompetitions();
  startAutoRefresh();
});

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId);
  }
});

// Rank badge styling
const getRankClass = (rank: number) => {
  switch (rank) {
    case 1: return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 2: return 'bg-slate-100 text-slate-700 border-slate-300';
    case 3: return 'bg-amber-100 text-amber-800 border-amber-300';
    default: return 'bg-white text-slate-600 border-slate-200';
  }
};
</script>

<template>
  <div class="py-8">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-slate-800 mb-2">Tabulator Dashboard</h1>
      <p class="text-slate-600">Live results with Irish Points calculation</p>
    </div>

    <!-- Filters Row -->
    <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-6 mb-6">
      <div class="grid md:grid-cols-3 gap-4">
        <!-- Feis Selector -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">Feis</label>
          <select
            v-model="selectedFeisId"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-300 bg-white text-slate-800 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all"
            :disabled="isLoadingFeiseanna"
          >
            <option :value="null">All Feiseanna</option>
            <option v-for="feis in feiseanna" :key="feis.id" :value="feis.id">
              {{ feis.name }}
            </option>
          </select>
        </div>

        <!-- Competition Selector -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">Competition</label>
          <select
            v-model="selectedCompetitionId"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-300 bg-white text-slate-800 focus:border-violet-500 focus:ring-2 focus:ring-violet-200 transition-all"
            :disabled="isLoadingCompetitions || filteredCompetitions.length === 0"
          >
            <option :value="null">Select a competition...</option>
            <option v-for="comp in filteredCompetitions" :key="comp.id" :value="comp.id">
              {{ comp.name }} ({{ comp.score_count }} scores)
            </option>
          </select>
          <p v-if="filteredCompetitions.length === 0 && !isLoadingCompetitions" class="text-sm text-slate-500 mt-1">
            No competitions with scores yet
          </p>
        </div>

        <!-- Auto-refresh & Manual Refresh -->
        <div class="flex items-end gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              v-model="autoRefresh"
              class="w-4 h-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
            />
            <span class="text-sm text-slate-600">Auto-refresh</span>
          </label>
          <button
            @click="fetchResults"
            :disabled="!selectedCompetitionId || isLoadingResults"
            class="px-4 py-2.5 rounded-lg font-medium bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
          >
            <svg v-if="isLoadingResults" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ isLoadingResults ? 'Refreshing...' : 'Refresh' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Results Display -->
    <div v-if="results" class="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      <!-- Results Header -->
      <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-5">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 class="text-xl font-bold text-white">{{ results.competition_name }}</h2>
            <p class="text-violet-200 text-sm">{{ results.feis_name }}</p>
          </div>
          <div class="flex items-center gap-6 text-sm">
            <div class="text-center">
              <div class="text-2xl font-bold text-white">{{ results.results.length }}</div>
              <div class="text-violet-200">Ranked</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-white">{{ results.judge_count }}</div>
              <div class="text-violet-200">{{ results.judge_count === 1 ? 'Judge' : 'Judges' }}</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-white">{{ results.total_scores }}</div>
              <div class="text-violet-200">Scores</div>
            </div>
          </div>
        </div>
        <div v-if="lastUpdated" class="mt-3 text-violet-200 text-xs">
          Last updated: {{ lastUpdated }}
        </div>
      </div>

      <!-- Results Table -->
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-slate-50 border-b border-slate-200">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider w-20">
                Rank
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider w-24">
                #
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Dancer
              </th>
              <th class="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                School
              </th>
              <th class="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider w-32">
                Irish Points
              </th>
              <th class="px-6 py-3 text-center text-xs font-semibold text-slate-600 uppercase tracking-wider w-24">
                Status
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr 
              v-for="(item, index) in results.results" 
              :key="index"
              :class="[
                'transition-colors',
                item.is_recalled ? 'bg-emerald-50/50' : 'hover:bg-slate-50'
              ]"
            >
              <!-- Rank -->
              <td class="px-6 py-4">
                <span 
                  :class="[
                    'inline-flex items-center justify-center w-8 h-8 rounded-full border-2 font-bold text-sm',
                    getRankClass(item.rank)
                  ]"
                >
                  {{ item.rank }}
                </span>
              </td>
              
              <!-- Competitor Number -->
              <td class="px-6 py-4 text-slate-600 font-mono">
                {{ item.competitor_number ?? '—' }}
              </td>
              
              <!-- Dancer Name -->
              <td class="px-6 py-4">
                <span class="font-medium text-slate-800">{{ item.dancer_name }}</span>
              </td>
              
              <!-- School -->
              <td class="px-6 py-4 text-slate-500 text-sm">
                {{ item.dancer_school ?? '—' }}
              </td>
              
              <!-- Irish Points -->
              <td class="px-6 py-4 text-right">
                <span class="font-mono font-semibold text-slate-800">
                  {{ item.irish_points.toFixed(2) }}
                </span>
              </td>
              
              <!-- Recall Status -->
              <td class="px-6 py-4 text-center">
                <span 
                  v-if="item.is_recalled"
                  class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800"
                >
                  <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                  </svg>
                  Recall
                </span>
                <span v-else class="text-slate-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div v-if="results.results.length === 0" class="px-6 py-12 text-center">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No results yet</h3>
        <p class="text-slate-500">Scores have been submitted but no complete results are available.</p>
      </div>
    </div>

    <!-- No Competition Selected State -->
    <div v-else-if="!selectedCompetitionId" class="bg-white rounded-xl shadow-lg border border-slate-200 p-12 text-center">
      <div class="w-20 h-20 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <svg class="w-10 h-10 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <h3 class="text-xl font-semibold text-slate-700 mb-2">Select a Competition</h3>
      <p class="text-slate-500 max-w-md mx-auto">
        Choose a feis and competition from the dropdowns above to view live results. 
        Only competitions with submitted scores will appear.
      </p>
    </div>

    <!-- Legend -->
    <div class="mt-6 flex flex-wrap items-center gap-6 text-sm text-slate-600">
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
          Recall
        </span>
        <span>Top 50% advance to finals (with tie extension)</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center justify-center w-6 h-6 rounded-full border-2 bg-yellow-100 text-yellow-800 border-yellow-300 text-xs font-bold">1</span>
        <span class="inline-flex items-center justify-center w-6 h-6 rounded-full border-2 bg-slate-100 text-slate-700 border-slate-300 text-xs font-bold">2</span>
        <span class="inline-flex items-center justify-center w-6 h-6 rounded-full border-2 bg-amber-100 text-amber-800 border-amber-300 text-xs font-bold">3</span>
        <span>Medal positions</span>
      </div>
    </div>
  </div>
</template>
