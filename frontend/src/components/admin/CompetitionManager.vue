<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import type { CompetitionLevel, Gender, CompetitionCategory } from '../../models/types';
import { useAuthStore } from '../../stores/auth';

interface Competition {
  id: string;
  feis_id: string;
  name: string;
  min_age: number;
  max_age: number;
  level: CompetitionLevel;
  gender?: Gender;
  code?: string;  // Display code (e.g., "407SJ")
  dance_type?: string;
  entry_count: number;
  category?: CompetitionCategory;
  description?: string;
  allowed_levels?: CompetitionLevel[];
}

const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const emit = defineEmits<{
  (e: 'back'): void;
  (e: 'generateSyllabus'): void;
}>();

// Auth store for authenticated requests
const auth = useAuthStore();

// State
const competitions = ref<Competition[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);

// Filters
const searchQuery = ref('');
const filterLevel = ref<string>('all');
const filterGender = ref<string>('all');

// Edit state
const editingComp = ref<Competition | null>(null);
const isCreating = ref(false);
const showModal = ref(false);

const editForm = ref({
  id: undefined as string | undefined,
  name: '',
  min_age: 0,
  max_age: 0,
  level: 'beginner_1' as CompetitionLevel,
  gender: null as Gender | null,
  code: '' as string,
  category: 'SOLO' as CompetitionCategory,
  description: '',
  allowed_levels: [] as CompetitionLevel[]
});

// Filtered competitions
const filteredCompetitions = computed(() => {
  let result = competitions.value;
  
  if (filterLevel.value !== 'all') {
    result = result.filter(c => c.level === filterLevel.value);
  }
  
  if (filterGender.value !== 'all') {
    if (filterGender.value === 'none') {
      result = result.filter(c => !c.gender);
    } else {
      result = result.filter(c => c.gender === filterGender.value);
    }
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(c => c.name.toLowerCase().includes(query));
  }
  
  return result;
});

// Stats
const stats = computed(() => ({
  total: competitions.value.length,
  withEntries: competitions.value.filter(c => c.entry_count > 0).length,
  empty: competitions.value.filter(c => c.entry_count === 0).length,
  totalEntries: competitions.value.reduce((sum, c) => sum + c.entry_count, 0)
}));

// Level options
const levelOptions = [
  { value: 'first_feis', label: 'First Feis' },
  { value: 'beginner_1', label: 'Beginner 1' },
  { value: 'beginner_2', label: 'Beginner 2' },
  { value: 'novice', label: 'Novice' },
  { value: 'prizewinner', label: 'Prizewinner' },
  { value: 'preliminary_championship', label: 'Prelim Champ' },
  { value: 'open_championship', label: 'Open Champ' }
];

// Gender options
const genderOptions = [
  { value: 'male', label: 'Boys' },
  { value: 'female', label: 'Girls' },
  { value: 'other', label: 'Open' }
];

// Category options
const categoryOptions = [
  { value: 'SOLO', label: 'Solo' },
  { value: 'FIGURE', label: 'Figure/Ceili' },
  { value: 'CHAMPIONSHIP', label: 'Championship' },
  { value: 'SPECIAL', label: 'Special' }
];

// Fetch competitions
const fetchCompetitions = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`/api/v1/feis/${props.feisId}/competitions`);
    if (!response.ok) throw new Error('Failed to fetch competitions');
    competitions.value = await response.json();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Start editing
const startEdit = (comp: Competition) => {
  editingComp.value = comp;
  isCreating.value = false;
  showModal.value = true;
  editForm.value = {
    id: comp.id,
    name: comp.name,
    min_age: comp.min_age,
    max_age: comp.max_age,
    level: comp.level,
    gender: comp.gender || null,
    code: comp.code || '',
    category: comp.category || 'SOLO',
    description: comp.description || '',
    allowed_levels: comp.allowed_levels || []
  };
};

// Start creating
const startCreate = () => {
  editingComp.value = null;
  isCreating.value = true;
  showModal.value = true;
  editForm.value = {
    id: undefined,
    name: 'New Competition',
    min_age: 5,
    max_age: 99,
    level: 'beginner_1',
    gender: null,
    code: '',
    category: 'SPECIAL',
    description: '',
    allowed_levels: []
  };
};

// Cancel editing
const cancelEdit = () => {
  editingComp.value = null;
  isCreating.value = false;
  showModal.value = false;
};

// Save edit
const saveEdit = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const payload = {
      ...editForm.value,
      feis_id: props.feisId // Ensure feis_id is included for create
    };
    
    // If Special category, ensure we send allowed_levels
    if (payload.category === 'SPECIAL' && payload.allowed_levels.length > 0) {
      // Logic handles multi-level
    }
    
    let response;
    if (isCreating.value) {
      // Use the general competitions creation endpoint
      response = await fetch(`/api/v1/competitions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } else {
      if (!editForm.value.id) return;
      response = await fetch(`/api/v1/competitions/${editForm.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    }

    if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to save competition');
    }
    
    const saved = await response.json();
    
    if (isCreating.value) {
      competitions.value.push(saved);
      successMessage.value = 'Competition created successfully';
    } else {
      const index = competitions.value.findIndex(c => c.id === saved.id);
    if (index !== -1) {
        competitions.value[index] = saved;
      }
      successMessage.value = 'Competition updated successfully';
    }
    
    cancelEdit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Delete competition
const deleteCompetition = async (comp: Competition) => {
  const message = comp.entry_count > 0
    ? `Delete "${comp.name}"? This will also delete ${comp.entry_count} entries. This cannot be undone.`
    : `Delete "${comp.name}"? This cannot be undone.`;
  
  if (!confirm(message)) return;
  
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`/api/v1/competitions/${comp.id}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to delete competition');
    
    competitions.value = competitions.value.filter(c => c.id !== comp.id);
    successMessage.value = 'Competition deleted successfully';
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Delete all empty competitions using bulk endpoint
const deleteEmptyCompetitions = async () => {
  const emptyCount = competitions.value.filter(c => c.entry_count === 0).length;
  if (emptyCount === 0) {
    successMessage.value = 'No empty competitions to delete';
    return;
  }
  
  if (!confirm(`Delete ${emptyCount} empty competitions? This cannot be undone.`)) return;
  
  loading.value = true;
  error.value = null;
  
  try {
    // Use the bulk delete endpoint
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/competitions/empty`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to delete empty competitions');
    }
    
    const result = await response.json();
    successMessage.value = result.message || `Deleted ${result.deleted_count} empty competitions`;
    
    // Refresh the list
    await fetchCompetitions();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
    console.error('Delete empty competitions error:', err);
  } finally {
    loading.value = false;
  }
};

// Clear messages
watch([successMessage, error], () => {
  if (successMessage.value) {
    setTimeout(() => successMessage.value = null, 5000);
  }
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

// Format gender display
const formatGender = (gender?: string) => {
  if (!gender) return 'Open';
  if (gender === 'male') return 'Boys';
  if (gender === 'female') return 'Girls';
  return gender.charAt(0).toUpperCase() + gender.slice(1);
};

// Format age range display
const formatAgeRange = (min: number, max: number): string => {
  if (min === max) {
    return `U${min + 1}`;
  }
  return `Ages ${min}-${max}`;
};

// Generate competition code from level, age, and dance type
const generateCode = (level: string, maxAge: number, danceType?: string): string => {
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
  const ageIndex = String(maxAge).padStart(2, '0');
  
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

// Computed: the effective code (user-entered or auto-generated)
const effectiveCode = computed(() => {
  if (editForm.value.code) return editForm.value.code;
  if (!editingComp.value) return '';
  return generateCode(
    editForm.value.level,
    editForm.value.max_age,
    editingComp.value.dance_type
  );
});

onMounted(() => {
  fetchCompetitions();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <button
          @click="emit('back')"
          class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Feis List
        </button>
        <h2 class="text-2xl font-bold text-slate-800">{{ feisName }}</h2>
        <p class="text-slate-600">Manage competitions</p>
      </div>
      <div class="flex gap-2">
        <button
          @click="startCreate"
          class="px-4 py-2 bg-white text-indigo-600 border border-indigo-200 rounded-lg font-medium hover:bg-indigo-50 transition-colors flex items-center gap-2"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Event
        </button>
      <button
        @click="emit('generateSyllabus')"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
          Bulk Generate
      </button>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
    </div>
    <div v-if="successMessage" class="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg">
      {{ successMessage }}
    </div>

    <!-- Stats & Actions -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-slate-800">{{ stats.total }}</div>
        <div class="text-slate-600 text-sm">Competitions</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-emerald-600">{{ stats.withEntries }}</div>
        <div class="text-slate-600 text-sm">With Entries</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-amber-600">{{ stats.empty }}</div>
        <div class="text-slate-600 text-sm">Empty</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-indigo-600">{{ stats.totalEntries }}</div>
        <div class="text-slate-600 text-sm">Total Entries</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200 flex items-center">
        <button
          @click="deleteEmptyCompetitions"
          :disabled="stats.empty === 0"
          class="w-full px-3 py-2 bg-red-100 text-red-700 rounded-lg font-medium hover:bg-red-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed transition-colors text-sm"
        >
          Delete Empty
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
      <div class="flex flex-wrap gap-4 items-center">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search competitions..."
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        
        <select
          v-model="filterLevel"
          class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          <option value="all">All Levels</option>
          <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        
        <select
          v-model="filterGender"
          class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          <option value="all">All Categories</option>
          <option v-for="opt in genderOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
          <option value="none">Open/Mixed</option>
        </select>
      </div>
    </div>

    <!-- Edit Modal -->
    <div 
      v-if="showModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="cancelEdit"
    >
      <div class="bg-white rounded-xl shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-bold text-slate-800 mb-4">{{ isCreating ? 'Add New Event' : 'Edit Competition' }}</h3>
        
        <form @submit.prevent="saveEdit" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Name</label>
            <input
              v-model="editForm.name"
              type="text"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Category</label>
            <select
              v-model="editForm.category"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div v-if="editForm.category === 'SPECIAL'">
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
                  v-model="editForm.allowed_levels"
                  class="rounded text-indigo-600 focus:ring-indigo-500"
                > 
                {{ opt.label }}
              </label>
            </div>
            <p class="text-xs text-slate-500 mt-1">Select all levels that can enter this event. Leave empty for "Open to All".</p>
          </div>
          
          <div v-else>
            <label class="block text-sm font-medium text-slate-700 mb-1">Level</label>
            <select
              v-model="editForm.level"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Min Age</label>
              <input
                v-model.number="editForm.min_age"
                type="number"
                min="4"
                max="99"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Max Age</label>
              <input
                v-model.number="editForm.max_age"
                type="number"
                :min="editForm.min_age"
                max="99"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Gender</label>
            <select
              v-model="editForm.gender"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option :value="null">Open/Mixed</option>
              <option v-for="opt in genderOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Description (Optional)</label>
            <textarea
              v-model="editForm.description"
              rows="3"
              placeholder="Describe the event, rules, or special awards..."
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            ></textarea>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">
              Code
            </label>
            <div class="relative">
              <input
                v-model="editForm.code"
                type="text"
                :placeholder="effectiveCode"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono text-lg tracking-wider placeholder:text-slate-400"
              />
              <span 
                v-if="!editForm.code && effectiveCode"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400"
              >
                default
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-1">
              Override with a custom value if needed
            </p>
          </div>
          
          <div class="flex gap-3 pt-2">
            <button
              type="submit"
              :disabled="loading"
              class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:bg-slate-300 transition-colors"
            >
              {{ isCreating ? 'Create Event' : 'Save Changes' }}
            </button>
            <button
              type="button"
              @click="cancelEdit"
              class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading && competitions.length === 0" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-indigo-200 border-t-indigo-600"></div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="competitions.length === 0"
      class="bg-white rounded-xl shadow p-12 text-center border border-slate-200"
    >
      <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Competitions Yet</h3>
      <p class="text-slate-500 mb-4">Generate a syllabus to create competitions.</p>
      <button
        @click="emit('generateSyllabus')"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
      >
        Generate Syllabus
      </button>
    </div>

    <!-- Competition Grid -->
    <div v-else class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="comp in filteredCompetitions"
        :key="comp.id"
        :class="[
          'bg-white rounded-lg shadow border p-4 hover:shadow-md transition-shadow',
          comp.entry_count === 0 ? 'border-amber-200' : 'border-slate-200'
        ]"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span 
                v-if="comp.code" 
                class="px-2 py-1 bg-indigo-100 text-indigo-700 rounded font-mono font-bold text-sm"
              >
                {{ comp.code }}
              </span>
              <h4 class="font-semibold text-slate-800">{{ comp.name }}</h4>
            </div>
            <div class="flex flex-wrap gap-2 mt-2">
              <span 
                v-if="comp.category === 'SPECIAL' && comp.allowed_levels && comp.allowed_levels.length > 0"
                class="px-2 py-0.5 bg-teal-100 text-teal-800 rounded text-xs"
              >
                {{ comp.allowed_levels.map(l => formatLevel(l)).join(', ') }}
              </span>
              <span 
                v-else-if="comp.category === 'SPECIAL'"
                class="px-2 py-0.5 bg-teal-100 text-teal-800 rounded text-xs"
              >
                Open to All Levels
              </span>
              <span 
                v-else
                class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs"
              >
                {{ formatLevel(comp.level) }}
              </span>
              
              <span class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs">
                {{ formatAgeRange(comp.min_age, comp.max_age) }}
              </span>
              <span class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs">
                {{ formatGender(comp.gender) }}
              </span>
              <span 
                v-if="comp.category !== 'SOLO'"
                class="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-medium"
              >
                {{ comp.category }}
              </span>
            </div>
            <div class="mt-2">
              <span 
                :class="[
                  'text-sm font-medium',
                  comp.entry_count > 0 ? 'text-emerald-600' : 'text-amber-600'
                ]"
              >
                {{ comp.entry_count }} {{ comp.entry_count === 1 ? 'entry' : 'entries' }}
              </span>
            </div>
          </div>
          
          <div class="flex gap-1 ml-2">
            <button
              @click="startEdit(comp)"
              class="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
              title="Edit"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click="deleteCompetition(comp)"
              class="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
              title="Delete"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- No Results -->
    <div 
      v-if="competitions.length > 0 && filteredCompetitions.length === 0"
      class="bg-white rounded-xl shadow p-8 text-center border border-slate-200"
    >
      <p class="text-slate-500">No competitions match your filters.</p>
    </div>
  </div>
</template>

