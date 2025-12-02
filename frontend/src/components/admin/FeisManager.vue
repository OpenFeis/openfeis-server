<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';

interface Feis {
  id: string;
  name: string;
  date: string;
  location: string;
  organizer_id: string;
  stripe_account_id?: string;
  competition_count: number;
  entry_count: number;
}

interface FeisForm {
  name: string;
  date: string;
  location: string;
}

const emit = defineEmits<{
  (e: 'select', feis: Feis): void;
}>();

// State
const feiseanna = ref<Feis[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const showCreateForm = ref(false);
const editingFeis = ref<Feis | null>(null);

// Form state
const form = ref<FeisForm>({
  name: '',
  date: new Date().toISOString().split('T')[0] ?? '',
  location: ''
});

// Form validation
const isFormValid = computed(() => {
  return form.value.name.trim().length >= 3 && 
         form.value.date && 
         form.value.location.trim().length >= 3;
});

// Fetch all feiseanna
const fetchFeiseanna = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch('/api/v1/feis');
    if (!response.ok) throw new Error('Failed to fetch feiseanna');
    feiseanna.value = await response.json();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Create new feis
const createFeis = async () => {
  if (!isFormValid.value) return;
  
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch('/api/v1/feis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    });
    if (!response.ok) throw new Error('Failed to create feis');
    
    const newFeis = await response.json();
    feiseanna.value.push(newFeis);
    resetForm();
    showCreateForm.value = false;
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Update feis
const updateFeis = async () => {
  if (!editingFeis.value || !isFormValid.value) return;
  
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`/api/v1/feis/${editingFeis.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    });
    if (!response.ok) throw new Error('Failed to update feis');
    
    const updated = await response.json();
    const index = feiseanna.value.findIndex(f => f.id === updated.id);
    if (index !== -1) {
      feiseanna.value[index] = updated;
    }
    cancelEdit();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Delete feis
const deleteFeis = async (feis: Feis) => {
  if (!confirm(`Delete "${feis.name}" and all its competitions and entries? This cannot be undone.`)) {
    return;
  }
  
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`/api/v1/feis/${feis.id}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error('Failed to delete feis');
    
    feiseanna.value = feiseanna.value.filter(f => f.id !== feis.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Edit mode
const startEdit = (feis: Feis) => {
  editingFeis.value = feis;
  form.value = {
    name: feis.name,
    date: feis.date,
    location: feis.location
  };
  showCreateForm.value = false;
};

const cancelEdit = () => {
  editingFeis.value = null;
  resetForm();
};

const resetForm = () => {
  form.value = {
    name: '',
    date: new Date().toISOString().split('T')[0] ?? '',
    location: ''
  };
};

// Format date for display
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
};

// Select feis for management
const selectFeis = (feis: Feis) => {
  emit('select', feis);
};

onMounted(() => {
  fetchFeiseanna();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-slate-800">Feis Management</h2>
        <p class="text-slate-600">Create and manage your feiseanna</p>
      </div>
      <button
        v-if="!showCreateForm && !editingFeis"
        @click="showCreateForm = true"
        class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        New Feis
      </button>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
    </div>

    <!-- Create/Edit Form -->
    <div 
      v-if="showCreateForm || editingFeis"
      class="bg-white rounded-xl shadow-lg border border-slate-200 p-6"
    >
      <h3 class="text-lg font-bold text-slate-800 mb-4">
        {{ editingFeis ? 'Edit Feis' : 'Create New Feis' }}
      </h3>
      
      <form @submit.prevent="editingFeis ? updateFeis() : createFeis()" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Feis Name</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="e.g., Great Irish Feis 2025"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Date</label>
          <input
            v-model="form.date"
            type="date"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Location</label>
          <input
            v-model="form.location"
            type="text"
            placeholder="e.g., Dublin Convention Center, Dublin, Ireland"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>
        
        <div class="flex gap-3 pt-2">
          <button
            type="submit"
            :disabled="!isFormValid || loading"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
          >
            {{ editingFeis ? 'Save Changes' : 'Create Feis' }}
          </button>
          <button
            type="button"
            @click="editingFeis ? cancelEdit() : (showCreateForm = false, resetForm())"
            class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>

    <!-- Loading State -->
    <div v-if="loading && feiseanna.length === 0" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-emerald-200 border-t-emerald-600"></div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="feiseanna.length === 0 && !showCreateForm"
      class="bg-white rounded-xl shadow-lg border border-slate-200 p-12 text-center"
    >
      <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Feiseanna Yet</h3>
      <p class="text-slate-500 mb-4">Create your first feis to get started.</p>
      <button
        @click="showCreateForm = true"
        class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors"
      >
        Create Your First Feis
      </button>
    </div>

    <!-- Feis List -->
    <div v-else class="grid gap-4">
      <div
        v-for="feis in feiseanna"
        :key="feis.id"
        class="bg-white rounded-xl shadow-lg border border-slate-200 p-6 hover:shadow-xl transition-shadow"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <h3 class="text-xl font-bold text-slate-800">{{ feis.name }}</h3>
            <p class="text-slate-600 mt-1">
              <span class="inline-flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {{ formatDate(feis.date) }}
              </span>
            </p>
            <p class="text-slate-600 mt-1">
              <span class="inline-flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {{ feis.location }}
              </span>
            </p>
            
            <!-- Stats -->
            <div class="flex gap-4 mt-4">
              <div class="bg-slate-100 px-3 py-1 rounded-lg">
                <span class="text-lg font-bold text-slate-800">{{ feis.competition_count }}</span>
                <span class="text-slate-600 text-sm ml-1">competitions</span>
              </div>
              <div class="bg-slate-100 px-3 py-1 rounded-lg">
                <span class="text-lg font-bold text-slate-800">{{ feis.entry_count }}</span>
                <span class="text-slate-600 text-sm ml-1">entries</span>
              </div>
            </div>
          </div>
          
          <!-- Actions -->
          <div class="flex flex-col gap-2 ml-4">
            <button
              @click="selectFeis(feis)"
              class="px-3 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors text-sm"
            >
              Manage
            </button>
            <button
              @click="startEdit(feis)"
              class="px-3 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors text-sm"
            >
              Edit
            </button>
            <button
              @click="deleteFeis(feis)"
              class="px-3 py-2 bg-red-100 text-red-700 rounded-lg font-medium hover:bg-red-200 transition-colors text-sm"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

