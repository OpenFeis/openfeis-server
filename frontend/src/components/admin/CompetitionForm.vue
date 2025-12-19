<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { CompetitionLevel, Gender, CompetitionCategory, DanceType, Stage, FeisAdjudicator } from '../../models/types';
import { DANCE_TYPE_INFO } from '../../models/types';

interface Competition {
  id?: string;
  feis_id?: string;
  name: string;
  min_age?: number;
  max_age?: number;
  level: CompetitionLevel;
  gender?: Gender | null;
  code?: string;
  category?: CompetitionCategory;
  description?: string;
  allowed_levels?: CompetitionLevel[];
  dance_type?: DanceType;
  entry_count?: number;
  // Scheduling fields
  stage_id?: string | null;
  scheduled_time?: string | null;
  estimated_duration_minutes?: number;
  adjudicator_id?: string | null;
}

const props = withDefaults(defineProps<{
  competition?: Competition | null;
  feisId: string;
  isCreating: boolean;
  stages?: Stage[];
  adjudicators?: FeisAdjudicator[];
}>(), {
  competition: null,
  stages: () => [],
  adjudicators: () => []
});

const emit = defineEmits<{
  (e: 'save', competition: Partial<Competition>): void;
  (e: 'cancel'): void;
}>();

const loading = ref(false);

// UI state for advanced level selector
const useMultipleLevels = ref(false);

// Form state
const form = ref<Competition>({
  feis_id: props.feisId,
  name: '',
  min_age: 5,
  max_age: 99,
  level: 'beginner_1',
  gender: null,
  code: '',
  category: 'SPECIAL',
  description: '',
  allowed_levels: [],
  estimated_duration_minutes: 15,
  stage_id: null,
  scheduled_time: null,
  adjudicator_id: null
});

// Options
const levelOptions = [
  { value: 'first_feis', label: 'First Feis' },
  { value: 'beginner_1', label: 'Beginner 1' },
  { value: 'beginner_2', label: 'Beginner 2' },
  { value: 'novice', label: 'Novice' },
  { value: 'prizewinner', label: 'Prizewinner' },
  { value: 'preliminary_championship', label: 'Prelim Champ' },
  { value: 'open_championship', label: 'Open Champ' }
];

const genderOptions = [
  { value: 'male', label: 'Boys' },
  { value: 'female', label: 'Girls' },
  { value: 'other', label: 'Open' }
];

const categoryOptions = [
  { value: 'SOLO', label: 'Solo' },
  { value: 'FIGURE', label: 'Figure/Ceili' },
  { value: 'CHAMPIONSHIP', label: 'Championship' },
  { value: 'SPECIAL', label: 'Special' }
];

// Auto-generate competition code
const generateCode = (level: string, maxAge: number | undefined, danceType?: DanceType): string => {
  const levelDigits: Record<string, string> = {
    first_feis: '1',
    beginner_1: '2',
    beginner_2: '3',
    novice: '4',
    prizewinner: '5',
    preliminary_championship: '6',
    open_championship: '7',
  };
  
  const danceCodes: Record<string, string> = {
    REEL: 'RL',
    LIGHT_JIG: 'LJ',
    SLIP_JIG: 'SJ',
    SINGLE_JIG: 'SN',
    TREBLE_JIG: 'TJ',
    HORNPIPE: 'HP',
    TRADITIONAL_SET: 'TS',
    CONTEMPORARY_SET: 'CS',
    TREBLE_REEL: 'TR',
  };
  
  const levelDigit = levelDigits[level] || '9';
  const ageIndex = String(maxAge || 99).padStart(2, '0');
  
  // For championships, use PC/OC instead of dance code
  if (level === 'preliminary_championship') {
    return `${levelDigit}${ageIndex}PC`;
  }
  if (level === 'open_championship') {
    return `${levelDigit}${ageIndex}OC`;
  }
  
  const danceCode = danceType ? (danceCodes[danceType] || danceType.substring(0, 2).toUpperCase()) : '';
  return `${levelDigit}${ageIndex}${danceCode}`;
};

// Computed: effective code (user-entered or auto-generated)
const effectiveCode = computed(() => {
  if (form.value.code) return form.value.code;
  return generateCode(
    form.value.level,
    form.value.max_age,
    form.value.dance_type
  );
});

// Format level display
const formatLevel = (level: string) => {
  const levelNames: Record<string, string> = {
    first_feis: 'First Feis',
    beginner_1: 'Beginner 1',
    beginner_2: 'Beginner 2',
    novice: 'Novice',
    prizewinner: 'Prizewinner',
    preliminary_championship: 'Prelim Champ',
    open_championship: 'Open Champ',
  };
  return levelNames[level] || level.charAt(0).toUpperCase() + level.slice(1);
};

// Get dance icon
const getDanceIcon = (danceType?: DanceType): string => {
  if (!danceType) return '🎵';
  return DANCE_TYPE_INFO[danceType]?.icon || '🎵';
};

// Initialize form from props
const initializeForm = () => {
  if (props.competition) {
    form.value = {
      ...form.value,
      ...props.competition,
      // Ensure allowed_levels is always an array
      allowed_levels: props.competition.allowed_levels || []
    };

    // Format scheduled time for datetime-local input without UTC shifting
    if (props.competition.scheduled_time) {
      const d = new Date(props.competition.scheduled_time);
      const year = d.getFullYear();
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      const hours = String(d.getHours()).padStart(2, '0');
      const minutes = String(d.getMinutes()).padStart(2, '0');
      form.value.scheduled_time = `${year}-${month}-${day}T${hours}:${minutes}`;
    } else {
      form.value.scheduled_time = null;
    }
    // Enable multi-level mode if this competition has allowed_levels set
    useMultipleLevels.value = !!(props.competition.category === 'SPECIAL' || 
      (props.competition.allowed_levels && props.competition.allowed_levels.length > 0));
  }
};

// Handle save
const handleSave = () => {
  const payload: Partial<Competition> = {
    ...form.value,
    feis_id: props.feisId
  };
  
  // If using multiple levels mode, ensure allowed_levels is set
  // Otherwise, clear allowed_levels and use single level
  if (useMultipleLevels.value) {
    payload.allowed_levels = form.value.allowed_levels;
  } else {
    payload.allowed_levels = [];
  }
  
  // Convert datetime-local to ISO string if provided
  if (form.value.scheduled_time) {
    payload.scheduled_time = form.value.scheduled_time + ':00';
  } else {
    payload.scheduled_time = null;
  }
  
  // Clean up null/empty values
  if (!payload.stage_id) payload.stage_id = null;
  if (!payload.adjudicator_id) payload.adjudicator_id = null;
  if (!payload.gender) payload.gender = null;
  if (!payload.code) payload.code = effectiveCode.value;
  
  emit('save', payload);
};

// Handle cancel
const handleCancel = () => {
  emit('cancel');
};

// Initialize on mount
onMounted(() => {
  initializeForm();
});

// Watch for competition changes
watch(() => props.competition, () => {
  initializeForm();
}, { deep: true });

// Auto-enable multi-level mode for SPECIAL category
watch(() => form.value.category, (newCategory) => {
  if (newCategory === 'SPECIAL') {
    useMultipleLevels.value = true;
  }
});
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-[100]"
    @click.self="handleCancel"
  >
    <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="bg-gradient-to-r from-indigo-600 to-blue-600 px-6 py-4 flex-shrink-0">
        <h3 class="text-xl font-bold text-white">
          {{ isCreating ? 'Add New Event' : 'Edit Competition' }}
        </h3>
        <p v-if="!isCreating && competition" class="text-indigo-100 text-sm mt-1">
          {{ competition.name }}
        </p>
      </div>

      <!-- Form Content -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5">
        <!-- Basic Information Section -->
        <div class="space-y-4">
          <h4 class="text-sm font-bold text-slate-700 uppercase tracking-wide border-b pb-2">Basic Information</h4>
          
          <!-- Competition Name -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Name</label>
            <input
              v-model="form.name"
              type="text"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="e.g., U11 Traditional Set (Open Championship)"
              required
            />
          </div>

          <!-- Category -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Category</label>
            <select
              v-model="form.category"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <!-- Level Selection Mode Toggle -->
          <div class="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg">
            <div>
              <label class="text-sm font-medium text-slate-700 cursor-pointer" @click="useMultipleLevels = !useMultipleLevels">
                Allow multiple levels
              </label>
              <p class="text-xs text-slate-500 mt-0.5">For events like Traditional Sets that accept dancers from multiple levels</p>
            </div>
            <button
              type="button"
              @click="useMultipleLevels = !useMultipleLevels"
              class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2"
              :class="useMultipleLevels ? 'bg-indigo-600' : 'bg-slate-300'"
            >
              <span
                class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                :class="useMultipleLevels ? 'translate-x-5' : 'translate-x-0'"
              ></span>
            </button>
          </div>

          <!-- Multi-Level Selection (when enabled) -->
          <div v-if="useMultipleLevels">
            <label class="block text-sm font-medium text-slate-700 mb-1">Allowed Levels</label>
            <div class="grid grid-cols-2 gap-2 p-3 border border-slate-200 rounded-lg bg-slate-50">
              <label 
                v-for="opt in levelOptions" 
                :key="opt.value"
                class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"
              >
                <input 
                  type="checkbox" 
                  :value="opt.value" 
                  v-model="form.allowed_levels"
                  class="rounded text-indigo-600 focus:ring-indigo-500"
                > 
                {{ opt.label }}
              </label>
            </div>
            <p class="text-xs text-slate-500 mt-1">Select all levels that can enter this event. Leave empty for "Open to All".</p>
          </div>

          <!-- Single Level Selection (standard mode) -->
          <div v-else>
            <label class="block text-sm font-medium text-slate-700 mb-1">Level</label>
            <select
              v-model="form.level"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <!-- Age Range -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Min Age</label>
              <input
                v-model.number="form.min_age"
                type="number"
                min="0"
                max="99"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Max Age</label>
              <input
                v-model.number="form.max_age"
                type="number"
                :min="form.min_age"
                max="99"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          <!-- Gender -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Gender</label>
            <select
              v-model="form.gender"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option :value="null">Open/Mixed</option>
              <option v-for="opt in genderOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Description (Optional)</label>
            <textarea
              v-model="form.description"
              rows="3"
              placeholder="Describe the event, rules, or special awards..."
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            ></textarea>
          </div>

          <!-- Code -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Code</label>
            <div class="relative">
              <input
                v-model="form.code"
                type="text"
                :placeholder="effectiveCode"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono text-lg tracking-wider placeholder:text-slate-400"
              />
              <span 
                v-if="!form.code && effectiveCode"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400"
              >
                default
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-1">Override with a custom value if needed</p>
          </div>
        </div>

        <!-- Scheduling Section (only show for existing competitions) -->
        <div v-if="!isCreating" class="space-y-4 pt-4 border-t border-slate-200">
          <h4 class="text-sm font-bold text-slate-700 uppercase tracking-wide border-b pb-2">Scheduling</h4>

          <!-- Entry Count & Level Info Badges -->
          <div class="flex items-center gap-3 text-sm flex-wrap">
            <div class="flex items-center gap-2 bg-slate-100 px-3 py-2 rounded-lg">
              <svg class="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              <span class="font-medium text-slate-700">{{ competition?.entry_count || 0 }} entries</span>
            </div>
            <div class="flex items-center gap-2 bg-slate-100 px-3 py-2 rounded-lg">
              <span class="font-medium text-slate-700">{{ formatLevel(form.level) }}</span>
            </div>
            <div v-if="competition?.dance_type" class="flex items-center gap-2 bg-slate-100 px-3 py-2 rounded-lg">
              <span>{{ getDanceIcon(competition.dance_type) }}</span>
              <span class="font-medium text-slate-700">{{ competition.dance_type.replace(/_/g, ' ') }}</span>
            </div>
          </div>

          <!-- Stage Assignment -->
          <div v-if="stages && stages.length > 0">
            <label class="block text-sm font-medium text-slate-700 mb-1">Stage</label>
            <select
              v-model="form.stage_id"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option :value="null">-- Unassigned --</option>
              <option 
                v-for="stage in stages" 
                :key="stage.id" 
                :value="stage.id"
              >
                {{ stage.name }}
              </option>
            </select>
          </div>

          <!-- Scheduled Time -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Scheduled Time</label>
            <input
              v-model="form.scheduled_time"
              type="datetime-local"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p class="text-xs text-slate-500 mt-1">Leave empty to unschedule</p>
          </div>

          <!-- Duration -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Estimated Duration (minutes)</label>
            <input
              v-model.number="form.estimated_duration_minutes"
              type="number"
              min="5"
              max="180"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          <!-- Adjudicator Assignment -->
          <div v-if="adjudicators && adjudicators.length > 0">
            <label class="block text-sm font-medium text-slate-700 mb-1">Assigned Judge</label>
            <select
              v-model="form.adjudicator_id"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option :value="null">-- No judge assigned --</option>
              <option 
                v-for="adj in adjudicators.filter(a => a.status === 'confirmed' || a.status === 'active')" 
                :key="adj.id" 
                :value="adj.user_id || adj.id"
              >
                {{ adj.name }}
                <template v-if="adj.credential"> ({{ adj.credential }})</template>
              </option>
            </select>
            <p class="text-xs text-slate-500 mt-1">Judges are auto-assigned based on stage coverage when you drag competitions</p>
          </div>

        </div>
      </div>

      <!-- Footer Actions -->
      <div class="flex gap-3 px-6 py-4 bg-slate-50 border-t border-slate-200 flex-shrink-0">
        <button
          type="submit"
          @click="handleSave"
          :disabled="loading || !form.name"
          class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
        >
          {{ isCreating ? 'Create Event' : 'Save Changes' }}
        </button>
        <button
          type="button"
          @click="handleCancel"
          class="px-6 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg font-medium hover:bg-slate-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

