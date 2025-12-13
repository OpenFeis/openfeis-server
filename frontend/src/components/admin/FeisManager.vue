<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';

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

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface CoOrganizer {
  id: string;
  feis_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  role: string;
  can_edit_feis: boolean;
  can_manage_entries: boolean;
  can_manage_schedule: boolean;
  can_manage_adjudicators: boolean;
  can_add_organizers: boolean;
  added_by: string;
  added_by_name: string;
  added_at: string;
}

interface OrganizerList {
  feis_id: string;
  feis_name: string;
  primary_organizer_id: string;
  primary_organizer_name: string;
  co_organizers: CoOrganizer[];
  total_organizers: number;
}

const emit = defineEmits<{
  (e: 'select', feis: Feis): void;
}>();

const authStore = useAuthStore();

// State
const feiseanna = ref<Feis[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const showCreateForm = ref(false);
const editingFeis = ref<Feis | null>(null);

// Co-organizer management state
const organizerData = ref<OrganizerList | null>(null);
const allUsers = ref<User[]>([]);
const userSearchQuery = ref('');
const selectedUser = ref<User | null>(null);
const showConfirmModal = ref(false);
const organizerLoading = ref(false);
const organizerError = ref<string | null>(null);

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

// Filtered users for search (exclude existing organizers)
const filteredUsers = computed(() => {
  if (!userSearchQuery.value.trim()) return [];
  
  const query = userSearchQuery.value.toLowerCase();
  const existingOrganizerIds = new Set<string>();
  
  if (organizerData.value) {
    existingOrganizerIds.add(organizerData.value.primary_organizer_id);
    organizerData.value.co_organizers.forEach(co => existingOrganizerIds.add(co.user_id));
  }
  
  return allUsers.value
    .filter(u => !existingOrganizerIds.has(u.id))
    .filter(u => 
      u.name.toLowerCase().includes(query) || 
      u.email.toLowerCase().includes(query)
    )
    .slice(0, 10); // Limit to 10 results
});

// Fetch feiseanna that the current user can manage
const fetchFeiseanna = async () => {
  loading.value = true;
  error.value = null;
  try {
    // Use /feis/mine to only get feiseanna this user can manage
    const response = await authStore.authFetch('/api/v1/feis/mine');
    if (!response.ok) throw new Error('Failed to fetch feiseanna');
    feiseanna.value = await response.json();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Fetch all users for search
const fetchUsers = async () => {
  try {
    const response = await authStore.authFetch('/api/v1/users');
    if (response.ok) {
      allUsers.value = await response.json();
    }
  } catch (err) {
    console.error('Failed to fetch users:', err);
  }
};

// Fetch organizers for a feis
const fetchOrganizers = async (feisId: string) => {
  organizerLoading.value = true;
  organizerError.value = null;
  try {
    const response = await authStore.authFetch(`/api/v1/feis/${feisId}/organizers`);
    if (response.ok) {
      organizerData.value = await response.json();
    } else {
      throw new Error('Failed to fetch organizers');
    }
  } catch (err) {
    organizerError.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    organizerLoading.value = false;
  }
};

// Select user to add as co-organizer
const selectUserToAdd = (user: User) => {
  selectedUser.value = user;
  userSearchQuery.value = '';
  showConfirmModal.value = true;
};

// Add co-organizer
const addCoOrganizer = async () => {
  if (!editingFeis.value || !selectedUser.value) return;
  
  organizerLoading.value = true;
  organizerError.value = null;
  try {
    const response = await authStore.authFetch(`/api/v1/feis/${editingFeis.value.id}/organizers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: selectedUser.value.id,
        role: 'co_organizer',
        can_edit_feis: true,
        can_manage_entries: true,
        can_manage_schedule: true,
        can_manage_adjudicators: true,
        can_add_organizers: false
      })
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to add co-organizer');
    }
    
    // Refresh organizer list
    await fetchOrganizers(editingFeis.value.id);
    
    // Close modal
    showConfirmModal.value = false;
    selectedUser.value = null;
  } catch (err) {
    organizerError.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    organizerLoading.value = false;
  }
};

// Remove co-organizer
const removeCoOrganizer = async (coOrganizer: CoOrganizer) => {
  if (!editingFeis.value) return;
  
  if (!confirm(`Remove ${coOrganizer.user_name} as co-organizer? They will no longer be able to manage this feis.`)) {
    return;
  }
  
  organizerLoading.value = true;
  organizerError.value = null;
  try {
    const response = await authStore.authFetch(`/api/v1/feis/${editingFeis.value.id}/organizers/${coOrganizer.id}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to remove co-organizer');
    }
    
    // Refresh organizer list
    await fetchOrganizers(editingFeis.value.id);
  } catch (err) {
    organizerError.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    organizerLoading.value = false;
  }
};

// Cancel confirmation modal
const cancelConfirm = () => {
  showConfirmModal.value = false;
  selectedUser.value = null;
};

// Create new feis
const createFeis = async () => {
  if (!isFormValid.value) return;
  
  loading.value = true;
  error.value = null;
  try {
    const response = await authStore.authFetch('/api/v1/feis', {
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
    const response = await authStore.authFetch(`/api/v1/feis/${editingFeis.value.id}`, {
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
    const response = await authStore.authFetch(`/api/v1/feis/${feis.id}`, {
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
const startEdit = async (feis: Feis) => {
  editingFeis.value = feis;
  form.value = {
    name: feis.name,
    date: feis.date,
    location: feis.location
  };
  showCreateForm.value = false;
  
  // Fetch organizers and users for co-organizer management
  await Promise.all([
    fetchOrganizers(feis.id),
    fetchUsers()
  ]);
};

const cancelEdit = () => {
  editingFeis.value = null;
  organizerData.value = null;
  userSearchQuery.value = '';
  selectedUser.value = null;
  organizerError.value = null;
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
      
      <!-- Co-Organizer Management (only when editing) -->
      <div v-if="editingFeis && organizerData" class="mt-8 pt-6 border-t border-slate-200">
        <h4 class="text-lg font-bold text-slate-800 mb-4">
          <svg class="w-5 h-5 inline-block mr-2 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          Organizers
        </h4>
        
        <!-- Error Message -->
        <div v-if="organizerError" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {{ organizerError }}
        </div>
        
        <!-- Primary Organizer -->
        <div class="mb-4">
          <p class="text-sm text-slate-500 mb-2">Primary Organizer (Owner)</p>
          <div class="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div class="w-10 h-10 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
              {{ organizerData.primary_organizer_name.charAt(0).toUpperCase() }}
            </div>
            <div>
              <p class="font-medium text-slate-800">{{ organizerData.primary_organizer_name }}</p>
              <p class="text-sm text-emerald-600">Owner</p>
            </div>
          </div>
        </div>
        
        <!-- Co-Organizers List -->
        <div class="mb-4">
          <p class="text-sm text-slate-500 mb-2">Co-Organizers ({{ organizerData.co_organizers.length }})</p>
          
          <div v-if="organizerData.co_organizers.length === 0" class="text-slate-400 text-sm p-4 bg-slate-50 rounded-lg text-center">
            No co-organizers yet. Add someone below to help manage this feis.
          </div>
          
          <div v-else class="space-y-2">
            <div 
              v-for="coOrg in organizerData.co_organizers" 
              :key="coOrg.id"
              class="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg"
            >
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-slate-400 rounded-full flex items-center justify-center text-white font-bold">
                  {{ coOrg.user_name.charAt(0).toUpperCase() }}
                </div>
                <div>
                  <p class="font-medium text-slate-800">{{ coOrg.user_name }}</p>
                  <p class="text-sm text-slate-500">{{ coOrg.user_email }}</p>
                </div>
              </div>
              <button
                @click="removeCoOrganizer(coOrg)"
                :disabled="organizerLoading"
                class="px-3 py-1.5 text-red-600 hover:bg-red-100 rounded-lg text-sm font-medium transition-colors"
              >
                Remove
              </button>
            </div>
          </div>
        </div>
        
        <!-- Add Co-Organizer Search -->
        <div class="relative">
          <p class="text-sm text-slate-500 mb-2">Add Co-Organizer</p>
          <input
            v-model="userSearchQuery"
            type="text"
            placeholder="Search by name or email..."
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
          
          <!-- Search Results Dropdown -->
          <div 
            v-if="filteredUsers.length > 0"
            class="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto"
          >
            <button
              v-for="user in filteredUsers"
              :key="user.id"
              type="button"
              @click="selectUserToAdd(user)"
              class="w-full px-4 py-3 text-left hover:bg-slate-50 border-b border-slate-100 last:border-b-0"
            >
              <p class="font-medium text-slate-800">{{ user.name }}</p>
              <p class="text-sm text-slate-500">{{ user.email }} • {{ user.role }}</p>
            </button>
          </div>
          
          <p class="mt-2 text-xs text-slate-400">
            Co-organizers can manage this feis but cannot delete it or add other organizers.
          </p>
        </div>
      </div>
      
      <!-- Loading spinner for organizer data -->
      <div v-if="editingFeis && organizerLoading && !organizerData" class="mt-8 pt-6 border-t border-slate-200 flex justify-center">
        <div class="animate-spin rounded-full h-8 w-8 border-4 border-emerald-200 border-t-emerald-600"></div>
      </div>
    </div>
    
    <!-- Confirmation Modal -->
    <div 
      v-if="showConfirmModal && selectedUser"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="cancelConfirm"
    >
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
        <h3 class="text-lg font-bold text-slate-800 mb-4">Add Co-Organizer</h3>
        
        <div class="flex items-center gap-4 p-4 bg-slate-50 rounded-lg mb-4">
          <div class="w-12 h-12 bg-emerald-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
            {{ selectedUser.name.charAt(0).toUpperCase() }}
          </div>
          <div>
            <p class="font-medium text-slate-800">{{ selectedUser.name }}</p>
            <p class="text-sm text-slate-500">{{ selectedUser.email }}</p>
            <p class="text-xs text-slate-400 mt-1">Current role: {{ selectedUser.role }}</p>
          </div>
        </div>
        
        <p class="text-slate-600 mb-4">
          Are you sure you want to add <strong>{{ selectedUser.name }}</strong> as a co-organizer for 
          <strong>{{ editingFeis?.name }}</strong>?
        </p>
        
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
          <p class="text-sm text-amber-800">
            <strong>Note:</strong> This user will be able to:
          </p>
          <ul class="text-sm text-amber-700 mt-1 ml-4 list-disc">
            <li>Edit feis details and settings</li>
            <li>Manage registrations and entries</li>
            <li>Edit the schedule</li>
            <li>Manage the adjudicator roster</li>
          </ul>
          <p class="text-sm text-amber-700 mt-2">
            They will keep their current role ({{ selectedUser.role }}) and its permissions.
          </p>
        </div>
        
        <div class="flex gap-3">
          <button
            @click="addCoOrganizer"
            :disabled="organizerLoading"
            class="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:bg-slate-300 transition-colors"
          >
            {{ organizerLoading ? 'Adding...' : 'Yes, Add as Co-Organizer' }}
          </button>
          <button
            @click="cancelConfirm"
            :disabled="organizerLoading"
            class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
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

