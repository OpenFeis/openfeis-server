<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { SchedulingDefaults, SchedulingDefaultsUpdateRequest } from '../../models/types';

// Props
const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved'): void;
}>();

const authStore = useAuthStore();

// State
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);

// Form data
const gradesJudgesPerStage = ref(1);
const champsJudgesPerPanel = ref(3);
const lunchDurationMinutes = ref(30);
const lunchWindowStart = ref('11:00');
const lunchWindowEnd = ref('13:00');

const API_BASE = '/api/v1';

// Fetch current defaults
async function fetchDefaults() {
  loading.value = true;
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/scheduling-defaults`);
    if (res.ok) {
      const data: SchedulingDefaults = await res.json();
      gradesJudgesPerStage.value = data.grades_judges_per_stage;
      champsJudgesPerPanel.value = data.champs_judges_per_panel;
      lunchDurationMinutes.value = data.lunch_duration_minutes;
      lunchWindowStart.value = data.lunch_window_start || '11:00';
      lunchWindowEnd.value = data.lunch_window_end || '13:00';
    }
  } catch (err) {
    console.error('Failed to fetch scheduling defaults:', err);
  } finally {
    loading.value = false;
  }
}

// Save defaults
async function saveDefaults() {
  saving.value = true;
  error.value = null;
  
  try {
    const updateData: SchedulingDefaultsUpdateRequest = {
      grades_judges_per_stage: gradesJudgesPerStage.value,
      champs_judges_per_panel: champsJudgesPerPanel.value,
      lunch_duration_minutes: lunchDurationMinutes.value,
      lunch_window_start: lunchWindowStart.value,
      lunch_window_end: lunchWindowEnd.value
    };
    
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/scheduling-defaults`, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to save defaults');
    }
    
    successMessage.value = 'Scheduling defaults saved!';
    setTimeout(() => { successMessage.value = null; }, 3000);
    emit('saved');
  } catch (err: any) {
    error.value = err.message || 'Failed to save defaults';
  } finally {
    saving.value = false;
  }
}

// Preset templates
const presets = [
  {
    name: 'Standard Local Feis',
    description: 'Single judge for grades, 3 judges for champs',
    gradesJudges: 1,
    champsJudges: 3,
    lunchMinutes: 30,
    lunchStart: '11:30',
    lunchEnd: '13:00'
  },
  {
    name: 'Championship Heavy',
    description: 'More time allocated for championship events',
    gradesJudges: 1,
    champsJudges: 3,
    lunchMinutes: 45,
    lunchStart: '12:00',
    lunchEnd: '14:00'
  },
  {
    name: 'Small Feis',
    description: 'Single panel for championships',
    gradesJudges: 1,
    champsJudges: 3,
    lunchMinutes: 30,
    lunchStart: '12:00',
    lunchEnd: '12:30'
  }
];

function applyPreset(preset: typeof presets[0]) {
  gradesJudgesPerStage.value = preset.gradesJudges;
  champsJudgesPerPanel.value = preset.champsJudges;
  lunchDurationMinutes.value = preset.lunchMinutes;
  lunchWindowStart.value = preset.lunchStart;
  lunchWindowEnd.value = preset.lunchEnd;
}

onMounted(fetchDefaults);
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-slate-800">Scheduling Defaults</h2>
        <p class="text-slate-600">{{ feisName }}</p>
      </div>
      <button
        @click="emit('close')"
        class="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Messages -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
      <button @click="error = null" class="float-right font-bold">&times;</button>
    </div>
    <div v-if="successMessage" class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
      {{ successMessage }}
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-emerald-200 border-t-emerald-600"></div>
    </div>

    <div v-else class="space-y-6">
      <!-- Presets -->
      <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
        <h3 class="text-lg font-bold text-slate-800 mb-4">Quick Presets</h3>
        <div class="grid md:grid-cols-3 gap-4">
          <button
            v-for="preset in presets"
            :key="preset.name"
            @click="applyPreset(preset)"
            class="p-4 border-2 border-slate-200 rounded-xl hover:border-emerald-500 hover:bg-emerald-50 transition-all text-left"
          >
            <div class="font-semibold text-slate-800">{{ preset.name }}</div>
            <div class="text-sm text-slate-500 mt-1">{{ preset.description }}</div>
          </button>
        </div>
      </div>

      <!-- Panel Rules -->
      <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
        <h3 class="text-lg font-bold text-slate-800 mb-4">Panel Configuration</h3>
        <div class="grid md:grid-cols-2 gap-6">
          <!-- Grades Judges -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Judges per Grade Stage
            </label>
            <div class="flex items-center gap-3">
              <input
                v-model.number="gradesJudgesPerStage"
                type="number"
                min="1"
                max="5"
                class="w-20 px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-center"
              />
              <span class="text-slate-500 text-sm">judge(s) per stage</span>
            </div>
            <p class="mt-2 text-sm text-slate-500">
              Typically 1 for grade competitions (Beginner, Novice, Prizewinner)
            </p>
          </div>

          <!-- Champs Judges -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Judges per Championship Panel
            </label>
            <div class="flex items-center gap-3">
              <input
                v-model.number="champsJudgesPerPanel"
                type="number"
                min="1"
                max="7"
                class="w-20 px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-center"
              />
              <span class="text-slate-500 text-sm">judges per panel</span>
            </div>
            <p class="mt-2 text-sm text-slate-500">
              Typically 3 for Prelim/Open Championships (or 5 for major events)
            </p>
          </div>
        </div>
      </div>

      <!-- Lunch Configuration -->
      <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
        <h3 class="text-lg font-bold text-slate-800 mb-4">Lunch Break</h3>
        <div class="grid md:grid-cols-3 gap-6">
          <!-- Duration -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Lunch Duration
            </label>
            <div class="flex items-center gap-3">
              <input
                v-model.number="lunchDurationMinutes"
                type="number"
                min="15"
                max="90"
                step="5"
                class="w-24 px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-center"
              />
              <span class="text-slate-500 text-sm">minutes</span>
            </div>
          </div>

          <!-- Window Start -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Preferred Start Time
            </label>
            <input
              v-model="lunchWindowStart"
              type="time"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <!-- Window End -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Preferred End Time
            </label>
            <input
              v-model="lunchWindowEnd"
              type="time"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
        </div>
        <p class="mt-4 text-sm text-slate-500">
          The scheduler will try to place lunch breaks within this window for all stages
        </p>
      </div>

      <!-- Summary Card -->
      <div class="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl p-6 text-white">
        <h3 class="text-lg font-semibold mb-3">Configuration Summary</h3>
        <div class="grid md:grid-cols-3 gap-4 text-sm">
          <div class="bg-white/20 rounded-lg p-3">
            <div class="text-emerald-100">Grade Competitions</div>
            <div class="text-xl font-bold">{{ gradesJudgesPerStage }} judge per stage</div>
          </div>
          <div class="bg-white/20 rounded-lg p-3">
            <div class="text-emerald-100">Championships</div>
            <div class="text-xl font-bold">{{ champsJudgesPerPanel }}-judge panels</div>
          </div>
          <div class="bg-white/20 rounded-lg p-3">
            <div class="text-emerald-100">Lunch Break</div>
            <div class="text-xl font-bold">{{ lunchDurationMinutes }} min</div>
            <div class="text-emerald-200 text-xs">{{ lunchWindowStart }} - {{ lunchWindowEnd }}</div>
          </div>
        </div>
      </div>

      <!-- Save Button -->
      <div class="flex justify-end gap-3">
        <button
          @click="emit('close')"
          class="px-6 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="saveDefaults"
          :disabled="saving"
          class="px-6 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:bg-slate-300 transition-colors flex items-center gap-2"
        >
          <template v-if="saving">
            <div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
            Saving...
          </template>
          <template v-else>
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            Save Defaults
          </template>
        </button>
      </div>
    </div>
  </div>
</template>

