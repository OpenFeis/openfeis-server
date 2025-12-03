<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useScoringStore } from '../../stores/scoring';
import { useAuthStore } from '../../stores/auth';
import type { CompetitorForScoring } from '../../models/types';

const store = useScoringStore();
const auth = useAuthStore();

// Local state
const selectedCompetitor = ref<CompetitorForScoring | null>(null);
const scoreInput = ref<number | null>(null);
const notesInput = ref<string>('');
const isSaving = ref(false);
const saveSuccess = ref(false);

// Group competitions by feis
const competitionsByFeis = computed(() => {
  const grouped: Record<string, { feisName: string; competitions: typeof store.competitions }> = {};
  
  for (const comp of store.competitions) {
    if (!grouped[comp.feis_id]) {
      grouped[comp.feis_id] = {
        feisName: comp.feis_name,
        competitions: []
      };
    }
    grouped[comp.feis_id]!.competitions.push(comp);
  }
  
  return grouped;
});

// Load competitions on mount
onMounted(async () => {
  if (auth.isAuthenticated) {
    await store.fetchCompetitions();
  }
});

// Select a competitor for scoring
function selectCompetitor(competitor: CompetitorForScoring) {
  selectedCompetitor.value = competitor;
  scoreInput.value = competitor.existing_score ?? null;
  notesInput.value = competitor.existing_notes ?? '';
  saveSuccess.value = false;
}

// Clear competitor selection
function clearCompetitor() {
  selectedCompetitor.value = null;
  scoreInput.value = null;
  notesInput.value = '';
  saveSuccess.value = false;
}

// Save score
async function saveScore() {
  if (!selectedCompetitor.value || scoreInput.value === null) return;
  
  isSaving.value = true;
  saveSuccess.value = false;
  
  try {
    const success = await store.submitScore(
      selectedCompetitor.value.entry_id,
      scoreInput.value,
      notesInput.value || undefined
    );
    
    if (success) {
      saveSuccess.value = true;
      // Auto-advance to next competitor after a brief delay
      setTimeout(() => {
        const currentIndex = store.competitors.findIndex(
          c => c.entry_id === selectedCompetitor.value?.entry_id
        );
        const nextCompetitor = store.competitors[currentIndex + 1];
        
        if (nextCompetitor) {
          selectCompetitor(nextCompetitor);
        } else {
          clearCompetitor();
        }
      }, 500);
    }
  } finally {
    isSaving.value = false;
  }
}

// Quick score buttons
function setQuickScore(value: number) {
  scoreInput.value = value;
}

// Get score status color
function getScoreColor(competitor: CompetitorForScoring): string {
  if (competitor.existing_score !== undefined && competitor.existing_score !== null) {
    return 'text-emerald-600 font-bold';
  }
  return 'text-slate-400';
}
</script>

<template>
  <div class="min-h-[calc(100vh-12rem)]">
    <!-- Login Required -->
    <div v-if="!auth.isAuthenticated" class="max-w-md mx-auto py-12 text-center">
      <div class="w-20 h-20 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-6">
        <svg class="w-10 h-10 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      </div>
      <h2 class="text-2xl font-bold text-slate-800 mb-3">Sign In Required</h2>
      <p class="text-slate-600">
        Please sign in with an adjudicator account to access the Judge Pad.
      </p>
    </div>

    <!-- Competition Selector -->
    <div v-else-if="!store.selectedCompetition" class="max-w-2xl mx-auto">
      <div class="bg-white rounded-2xl shadow-lg p-6">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h1 class="text-2xl font-bold text-slate-800">Judge Pad</h1>
            <p class="text-slate-600">Select a competition to score</p>
          </div>
          <div class="flex items-center gap-2">
            <span 
              :class="[
                'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium',
                store.isOnline 
                  ? 'bg-emerald-100 text-emerald-700' 
                  : 'bg-amber-100 text-amber-700'
              ]"
            >
              <span :class="['w-2 h-2 rounded-full', store.isOnline ? 'bg-emerald-500' : 'bg-amber-500']"></span>
              {{ store.isOnline ? 'Online' : 'Offline' }}
            </span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="store.isLoading" class="py-12 text-center">
          <div class="animate-spin w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p class="text-slate-600">Loading competitions...</p>
        </div>

        <!-- Error -->
        <div v-else-if="store.error" class="py-8 text-center">
          <p class="text-red-600 mb-4">{{ store.error }}</p>
          <button 
            @click="store.fetchCompetitions()"
            class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
          >
            Try Again
          </button>
        </div>

        <!-- No Competitions -->
        <div v-else-if="store.competitions.length === 0" class="py-12 text-center">
          <div class="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-800 mb-2">No Competitions Available</h3>
          <p class="text-slate-600 text-sm">
            There are no competitions with assigned competitor numbers yet.<br>
            Ask the organizer to assign numbers before scoring can begin.
          </p>
        </div>

        <!-- Competition List -->
        <div v-else class="space-y-6">
          <div v-for="(group, feisId) in competitionsByFeis" :key="feisId">
            <h3 class="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">
              {{ group.feisName }}
            </h3>
            <div class="space-y-2">
              <button
                v-for="comp in group.competitions"
                :key="comp.id"
                @click="store.selectCompetition(comp)"
                class="w-full p-4 bg-slate-50 hover:bg-slate-100 rounded-xl text-left transition-colors flex items-center justify-between group"
              >
                <div>
                  <p class="font-semibold text-slate-800 group-hover:text-emerald-700 transition-colors">
                    {{ comp.name }}
                  </p>
                  <p class="text-sm text-slate-500">
                    {{ comp.competitor_count }} competitor{{ comp.competitor_count !== 1 ? 's' : '' }}
                    • {{ comp.level }}
                  </p>
                </div>
                <svg class="w-5 h-5 text-slate-400 group-hover:text-emerald-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Scoring Interface -->
    <div v-else class="max-w-4xl mx-auto">
      <!-- Header -->
      <div class="bg-white rounded-2xl shadow-lg p-4 mb-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <button
              @click="store.clearCompetition()"
              class="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <svg class="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div>
              <h1 class="font-bold text-slate-800">{{ store.selectedCompetition.name }}</h1>
              <p class="text-sm text-slate-500">{{ store.selectedCompetition.feis_name }}</p>
            </div>
          </div>
          <span 
            :class="[
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium',
              store.isOnline 
                ? 'bg-emerald-100 text-emerald-700' 
                : 'bg-amber-100 text-amber-700'
            ]"
          >
            <span :class="['w-2 h-2 rounded-full', store.isOnline ? 'bg-emerald-500' : 'bg-amber-500']"></span>
            {{ store.isOnline ? 'Online' : 'Saving Locally' }}
          </span>
        </div>
      </div>

      <div class="grid md:grid-cols-2 gap-4">
        <!-- Competitor List -->
        <div class="bg-white rounded-2xl shadow-lg p-4">
          <h2 class="font-semibold text-slate-800 mb-3">
            Competitors ({{ store.competitors.length }})
          </h2>
          
          <div v-if="store.isLoading" class="py-8 text-center">
            <div class="animate-spin w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full mx-auto"></div>
          </div>
          
          <div v-else class="space-y-1 max-h-[60vh] overflow-y-auto">
            <button
              v-for="competitor in store.competitors"
              :key="competitor.entry_id"
              @click="selectCompetitor(competitor)"
              :class="[
                'w-full p-3 rounded-lg text-left transition-all flex items-center justify-between',
                selectedCompetitor?.entry_id === competitor.entry_id
                  ? 'bg-emerald-100 border-2 border-emerald-500'
                  : 'bg-slate-50 hover:bg-slate-100 border-2 border-transparent'
              ]"
            >
              <div>
                <p class="font-mono font-bold text-lg text-slate-800">
                  #{{ competitor.competitor_number }}
                </p>
                <p class="text-sm text-slate-600">{{ competitor.dancer_name }}</p>
                <p v-if="competitor.dancer_school" class="text-xs text-slate-400">
                  {{ competitor.dancer_school }}
                </p>
              </div>
              <div :class="getScoreColor(competitor)" class="text-xl font-mono">
                {{ competitor.existing_score ?? '—' }}
              </div>
            </button>
          </div>
        </div>

        <!-- Score Entry -->
        <div class="bg-white rounded-2xl shadow-lg p-4">
          <div v-if="!selectedCompetitor" class="py-12 text-center text-slate-500">
            <svg class="w-12 h-12 mx-auto mb-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
            </svg>
            <p>Select a competitor to score</p>
          </div>

          <div v-else>
            <div class="mb-6">
              <div class="flex items-center justify-between mb-2">
                <h2 class="text-2xl font-bold text-slate-800">
                  #{{ selectedCompetitor.competitor_number }}
                </h2>
                <button
                  @click="clearCompetitor"
                  class="text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <p class="text-slate-600">{{ selectedCompetitor.dancer_name }}</p>
            </div>

            <!-- Score Input -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-700 mb-2">Score (0-100)</label>
              <input
                type="number"
                v-model="scoreInput"
                min="0"
                max="100"
                step="0.5"
                class="w-full px-4 py-4 text-3xl font-mono text-center border-2 border-slate-200 rounded-xl focus:border-emerald-500 focus:ring-0 transition-colors"
                placeholder="—"
              />
            </div>

            <!-- Quick Score Buttons -->
            <div class="grid grid-cols-5 gap-2 mb-4">
              <button
                v-for="score in [60, 70, 75, 80, 85]"
                :key="score"
                @click="setQuickScore(score)"
                :class="[
                  'py-2 rounded-lg font-mono font-medium transition-colors',
                  scoreInput === score
                    ? 'bg-emerald-500 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                ]"
              >
                {{ score }}
              </button>
            </div>

            <!-- Notes -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-slate-700 mb-2">Notes (optional)</label>
              <textarea
                v-model="notesInput"
                rows="3"
                class="w-full px-3 py-2 border-2 border-slate-200 rounded-xl focus:border-emerald-500 focus:ring-0 transition-colors resize-none"
                placeholder="Timing, technique, presentation..."
              ></textarea>
            </div>

            <!-- Save Button -->
            <button
              @click="saveScore"
              :disabled="scoreInput === null || isSaving"
              :class="[
                'w-full py-4 rounded-xl font-bold text-lg transition-all',
                scoreInput === null
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : saveSuccess
                    ? 'bg-emerald-500 text-white'
                    : 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-200 hover:shadow-xl'
              ]"
            >
              <span v-if="isSaving" class="flex items-center justify-center gap-2">
                <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving...
              </span>
              <span v-else-if="saveSuccess" class="flex items-center justify-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                Saved!
              </span>
              <span v-else>Save Score</span>
            </button>

            <!-- Offline Notice -->
            <p v-if="!store.isOnline" class="mt-3 text-center text-sm text-amber-600">
              ⚠️ You're offline. Scores will sync when you reconnect.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
