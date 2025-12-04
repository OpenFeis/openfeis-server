<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import type { 
  Competition,
  Feis,
  Stage
} from '../../models/types';

const props = defineProps<{
  feisId?: string;
  stageId?: string;
}>();

// State
const loading = ref(true);

// Available selections - stage-centric workflow
const feiseanna = ref<Feis[]>([]);
const stages = ref<Stage[]>([]);
const competitions = ref<Competition[]>([]);
const selectedFeis = ref<string>(props.feisId || '');
const selectedStage = ref<string>(props.stageId || '');

// Current position in the schedule (which competition is "now")
const currentIndex = ref(0);

// Full screen mode
const isFullScreen = ref(false);

// Auto-advance timer
const autoAdvance = ref(false);
const autoAdvanceInterval = ref<number | null>(null);

// Refresh interval
const refreshInterval = ref<number | null>(null);

// Current stage info
const currentStage = computed(() => {
  return stages.value.find(s => s.id === selectedStage.value);
});

// Competitions filtered to selected stage, sorted by scheduled time
const stageCompetitions = computed(() => {
  if (!selectedStage.value) return [];
  return competitions.value
    .filter(c => c.stage_id === selectedStage.value)
    .sort((a, b) => {
      if (!a.scheduled_time && !b.scheduled_time) return 0;
      if (!a.scheduled_time) return 1;
      if (!b.scheduled_time) return -1;
      return new Date(a.scheduled_time).getTime() - new Date(b.scheduled_time).getTime();
    });
});

// Display competitions: current + next (only 2)
const currentCompetition = computed(() => {
  return stageCompetitions.value[currentIndex.value];
});

const nextCompetition = computed(() => {
  return stageCompetitions.value[currentIndex.value + 1];
});

// Get display code for a competition
const getDisplayCode = (comp: Competition): string => {
  // Use the code field if available
  if (comp.code) {
    return comp.code;
  }
  // Fallback: use name truncated
  return comp.name.substring(0, 12).toUpperCase();
};

// Fetch feiseanna
const fetchFeiseanna = async () => {
  try {
    const response = await fetch('/api/v1/feis');
    if (response.ok) {
      feiseanna.value = await response.json();
      const firstFeis = feiseanna.value[0];
      if (!selectedFeis.value && firstFeis) {
        selectedFeis.value = firstFeis.id;
      }
    }
  } catch (e) {
    console.error('Failed to fetch feiseanna:', e);
  }
};

// Fetch stages for selected feis
const fetchStages = async () => {
  if (!selectedFeis.value) {
    stages.value = [];
    return;
  }
  
  try {
    const response = await fetch(`/api/v1/feis/${selectedFeis.value}/stages`);
    if (response.ok) {
      stages.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch stages:', e);
  }
};

// Fetch all competitions
const fetchCompetitions = async () => {
  if (!selectedFeis.value) {
    competitions.value = [];
    return;
  }
  
  try {
    const response = await fetch(`/api/v1/feis/${selectedFeis.value}/competitions`);
    if (response.ok) {
      competitions.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch competitions:', e);
  } finally {
    loading.value = false;
  }
};

// Auto-select current competition based on time
const autoSelectCurrent = () => {
  if (stageCompetitions.value.length === 0) {
    currentIndex.value = 0;
    return;
  }
  
  const now = new Date();
  let bestIndex = 0;
  
  for (let i = 0; i < stageCompetitions.value.length; i++) {
    const comp = stageCompetitions.value[i];
    if (comp?.scheduled_time) {
      const compTime = new Date(comp.scheduled_time);
      if (compTime <= now) {
        bestIndex = i;
      }
    }
  }
  
  currentIndex.value = bestIndex;
};

// Navigation
const goNext = () => {
  if (currentIndex.value < stageCompetitions.value.length - 1) {
    currentIndex.value++;
  }
};

const goPrev = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--;
  }
};

// Toggle fullscreen
const toggleFullScreen = async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen();
    isFullScreen.value = true;
  } else {
    await document.exitFullscreen();
    isFullScreen.value = false;
  }
};

// Toggle auto-advance
const toggleAutoAdvance = () => {
  autoAdvance.value = !autoAdvance.value;
  if (autoAdvance.value) {
    startAutoAdvance();
  } else {
    stopAutoAdvance();
  }
};

const startAutoAdvance = () => {
  stopAutoAdvance();
  // Auto-advance every 3 minutes (typical competition duration)
  autoAdvanceInterval.value = window.setInterval(() => {
    if (currentIndex.value < stageCompetitions.value.length - 1) {
      currentIndex.value++;
    }
  }, 180000);
};

const stopAutoAdvance = () => {
  if (autoAdvanceInterval.value) {
    clearInterval(autoAdvanceInterval.value);
    autoAdvanceInterval.value = null;
  }
};

// Watchers
watch(selectedFeis, () => {
  selectedStage.value = '';
  currentIndex.value = 0;
  fetchStages();
  fetchCompetitions();
});

watch(selectedStage, () => {
  autoSelectCurrent();
});

watch(stageCompetitions, () => {
  // Re-sync position when competitions update
  if (currentIndex.value >= stageCompetitions.value.length) {
    currentIndex.value = Math.max(0, stageCompetitions.value.length - 1);
  }
});

onMounted(async () => {
  await fetchFeiseanna();
  if (selectedFeis.value) {
    await fetchStages();
    await fetchCompetitions();
  }
  if (selectedStage.value) {
    autoSelectCurrent();
  }
  
  // Refresh competitions periodically (in case schedule changes)
  refreshInterval.value = window.setInterval(() => {
    fetchCompetitions();
  }, 60000);
  
  document.addEventListener('fullscreenchange', () => {
    isFullScreen.value = !!document.fullscreenElement;
  });
  
  // Keyboard navigation
  document.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  stopAutoAdvance();
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value);
  }
  document.removeEventListener('keydown', handleKeyDown);
});

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowRight' || e.key === ' ') {
    e.preventDefault();
    goNext();
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
    e.preventDefault();
    goPrev();
  } else if (e.key === 'f' || e.key === 'F') {
    toggleFullScreen();
  }
};
</script>

<template>
  <!-- 
    Use fixed positioning for fullscreen to ensure it covers the entire viewport.
    The min-h-screen doesn't work reliably across all browsers in fullscreen mode.
  -->
  <div 
    :class="[
      'transition-all',
      isFullScreen 
        ? 'fixed inset-0 z-[9999]' 
        : 'min-h-screen'
    ]"
    :style="{
      background: currentStage?.color 
        ? `linear-gradient(180deg, ${currentStage.color}20 0%, #1e293b 50%, #0f172a 100%)`
        : 'linear-gradient(180deg, #334155 0%, #1e293b 50%, #0f172a 100%)'
    }"
  >
    <!-- Header Controls (hidden in fullscreen) -->
    <div v-if="!isFullScreen" class="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-3">
      <div class="flex flex-wrap items-center gap-4">
        <div class="flex items-center gap-3">
          <div 
            class="w-10 h-10 rounded-xl flex items-center justify-center"
            :style="currentStage?.color ? { background: currentStage.color } : {}"
            :class="!currentStage?.color ? 'bg-gradient-to-br from-emerald-500 to-teal-600' : ''"
          >
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h1 class="text-lg font-bold text-white">Stage Monitor</h1>
          </div>
        </div>

        <!-- Selectors -->
        <div class="flex-1 flex flex-wrap items-center gap-3">
          <select
            v-model="selectedFeis"
            class="px-3 py-2 bg-slate-700 text-white border border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 text-sm"
          >
            <option value="">Select Feis</option>
            <option v-for="feis in feiseanna" :key="feis.id" :value="feis.id">
              {{ feis.name }}
            </option>
          </select>

          <select
            v-model="selectedStage"
            :disabled="!selectedFeis || stages.length === 0"
            class="px-3 py-2 bg-slate-700 text-white border border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500 disabled:opacity-50 text-sm"
          >
            <option value="">Select Stage</option>
            <option v-for="stage in stages" :key="stage.id" :value="stage.id">
              {{ stage.name }}
            </option>
          </select>
        </div>

        <!-- Controls -->
        <div class="flex items-center gap-2">
          <button
            @click="goPrev"
            :disabled="currentIndex === 0"
            class="p-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 disabled:opacity-30 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            </svg>
          </button>
          
          <button
            @click="goNext"
            :disabled="currentIndex >= stageCompetitions.length - 1"
            class="p-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 disabled:opacity-30 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <button
            @click="toggleAutoAdvance"
            :class="[
              'px-3 py-2 rounded-lg text-sm transition-colors',
              autoAdvance ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            ]"
          >
            {{ autoAdvance ? 'Auto ●' : 'Auto' }}
          </button>

          <button
            @click="toggleFullScreen"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors flex items-center gap-2 text-sm"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
            Full Screen
          </button>
        </div>
      </div>
    </div>

    <!-- Fullscreen Controls (minimal) -->
    <div v-if="isFullScreen" class="absolute top-6 right-6 z-50 flex items-center gap-3">
      <button
        @click="goPrev"
        :disabled="currentIndex === 0"
        class="p-4 bg-slate-800/70 text-white rounded-2xl hover:bg-slate-700 disabled:opacity-30 transition-colors"
      >
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
        </svg>
      </button>
      
      <button
        @click="goNext"
        :disabled="currentIndex >= stageCompetitions.length - 1"
        class="p-4 bg-slate-800/70 text-white rounded-2xl hover:bg-slate-700 disabled:opacity-30 transition-colors"
      >
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      <button
        @click="toggleFullScreen"
        class="p-4 bg-slate-800/70 text-white rounded-2xl hover:bg-slate-700 transition-colors"
      >
        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Stage Name Header (fullscreen only) -->
    <div 
      v-if="isFullScreen && currentStage" 
      class="absolute top-6 left-6 z-50 px-8 py-4 rounded-2xl font-black text-3xl text-white tracking-wide"
      :style="currentStage.color ? { background: currentStage.color } : {}"
      :class="!currentStage.color ? 'bg-emerald-600' : ''"
    >
      {{ currentStage.name }}
    </div>

    <!-- Main Content -->
    <div 
      class="flex flex-col items-center justify-center"
      :class="isFullScreen ? 'h-full' : 'h-[calc(100vh-80px)]'"
    >
      <!-- Empty states -->
      <template v-if="!selectedStage">
        <div class="text-center text-slate-400">
          <svg class="w-24 h-24 mx-auto mb-6 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <p class="text-3xl font-light">Select a stage</p>
        </div>
      </template>

      <template v-else-if="loading">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-emerald-500/30 border-t-emerald-500"></div>
      </template>

      <template v-else-if="stageCompetitions.length === 0">
        <div class="text-center text-slate-400">
          <p class="text-3xl font-light">No competitions scheduled</p>
        </div>
      </template>

      <!-- Competition Display - Only 2 items -->
      <template v-else>
        <!-- Stage name (non-fullscreen) -->
        <div v-if="!isFullScreen && currentStage" class="mb-8">
          <span 
            class="px-6 py-2 rounded-full font-bold text-xl text-white"
            :style="currentStage.color ? { background: currentStage.color } : {}"
            :class="!currentStage.color ? 'bg-emerald-600' : ''"
          >
            {{ currentStage.name }}
          </span>
        </div>

        <!-- Current Competition - NOW -->
        <div v-if="currentCompetition" class="text-center mb-12">
          <div 
            class="text-emerald-400 font-semibold uppercase tracking-[0.4em] mb-4"
            :class="isFullScreen ? 'text-2xl' : 'text-lg'"
          >
            Now
          </div>
          <div 
            class="font-black text-white leading-none tracking-wider"
            :class="isFullScreen ? 'text-[20rem]' : 'text-[12rem]'"
            :style="currentStage?.color ? { textShadow: `0 0 80px ${currentStage.color}50` } : {}"
          >
            {{ getDisplayCode(currentCompetition) }}
          </div>
          <div 
            class="text-slate-400 mt-4"
            :class="isFullScreen ? 'text-3xl' : 'text-xl'"
          >
            {{ currentCompetition.name }}
          </div>
        </div>

        <!-- Next Competition - NEXT -->
        <div v-if="nextCompetition" class="text-center opacity-50">
          <div 
            class="text-amber-400/70 font-semibold uppercase tracking-[0.3em] mb-2"
            :class="isFullScreen ? 'text-xl' : 'text-sm'"
          >
            Next
          </div>
          <div 
            class="font-black text-white/60 leading-none tracking-wider"
            :class="isFullScreen ? 'text-[8rem]' : 'text-[5rem]'"
          >
            {{ getDisplayCode(nextCompetition) }}
          </div>
        </div>

        <!-- Position indicator -->
        <div 
          class="absolute bottom-8 left-1/2 -translate-x-1/2 text-slate-500"
          :class="isFullScreen ? 'text-xl' : 'text-sm'"
        >
          {{ currentIndex + 1 }} / {{ stageCompetitions.length }}
        </div>
      </template>
    </div>

    <!-- Keyboard hint (non-fullscreen) -->
    <div 
      v-if="!isFullScreen && selectedStage && stageCompetitions.length > 0" 
      class="fixed bottom-4 left-1/2 -translate-x-1/2 text-slate-500 text-xs"
    >
      Press <kbd class="px-1.5 py-0.5 bg-slate-700 rounded">↑</kbd> <kbd class="px-1.5 py-0.5 bg-slate-700 rounded">↓</kbd> to navigate, <kbd class="px-1.5 py-0.5 bg-slate-700 rounded">F</kbd> for fullscreen
    </div>
  </div>
</template>
