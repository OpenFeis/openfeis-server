<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { 
  FeisAdjudicator, 
  AdjudicatorListResponse,
  AdjudicatorCapacity,
  AdjudicatorCreateRequest,
  AdjudicatorUpdateRequest,
  User
} from '../../models/types';
import { 
  getAdjudicatorStatusBadge, 
  ADJUDICATOR_CREDENTIALS, 
  DANCE_ORGANIZATIONS 
} from '../../models/types';
import PanelsManager from './PanelsManager.vue';

// Props
const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const authStore = useAuthStore();

// Tab state
const activeTab = ref<'judges' | 'panels'>('judges');

// State
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);

// Data
const adjudicators = ref<FeisAdjudicator[]>([]);
const capacity = ref<AdjudicatorCapacity | null>(null);
const teachers = ref<User[]>([]);  // For school affiliation dropdown

// Counts
const totalCount = ref(0);
const confirmedCount = ref(0);
const invitedCount = ref(0);
const activeCount = ref(0);

// Modal state
const showAddModal = ref(false);
const editingAdjudicator = ref<FeisAdjudicator | null>(null);
const showInviteLinkModal = ref(false);
const inviteLink = ref('');
const showPinModal = ref(false);
const generatedPin = ref('');
const pinAdjudicatorName = ref('');

// User search state (typeahead)
const searchQuery = ref('');
const searchResults = ref<User[]>([]);
const showSearchResults = ref(false);
const selectedUser = ref<User | null>(null);
const isSearching = ref(false);
let searchTimeout: ReturnType<typeof setTimeout> | null = null;

// Form data
const form = ref<AdjudicatorCreateRequest>({
  name: '',
  email: '',
  phone: '',
  credential: '',
  organization: '',
  school_affiliation_id: '',
  user_id: ''
});

const API_BASE = '/api/v1';

// Computed
const isFormValid = computed(() => {
  return form.value.name.trim().length >= 2;
});

// Fetch functions
async function fetchAdjudicators() {
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/adjudicators`);
    if (res.ok) {
      const data: AdjudicatorListResponse = await res.json();
      adjudicators.value = data.adjudicators;
      totalCount.value = data.total_adjudicators;
      confirmedCount.value = data.confirmed_count;
      invitedCount.value = data.invited_count;
      activeCount.value = data.active_count;
    }
  } catch (err) {
    console.error('Failed to fetch adjudicators:', err);
  }
}

async function fetchCapacity() {
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/adjudicator-capacity`);
    if (res.ok) {
      capacity.value = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch capacity:', err);
  }
}

async function fetchTeachers() {
  try {
    // Get all users with teacher role for school affiliation dropdown
    const res = await authStore.authFetch(`${API_BASE}/users`);
    if (res.ok) {
      const allUsers: User[] = await res.json();
      teachers.value = allUsers.filter(u => u.role === 'teacher' || u.role === 'organizer' || u.role === 'super_admin');
    }
  } catch (err) {
    console.error('Failed to fetch teachers:', err);
  }
}

// CRUD operations
async function createAdjudicator() {
  saving.value = true;
  error.value = null;
  
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/adjudicators`, {
      method: 'POST',
      body: JSON.stringify(form.value)
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to add adjudicator');
    }
    
    await fetchAdjudicators();
    await fetchCapacity();
    showAddModal.value = false;
    resetForm();
    successMessage.value = 'Adjudicator added to roster!';
    setTimeout(() => { successMessage.value = null; }, 3000);
  } catch (err: any) {
    error.value = err.message || 'Failed to add adjudicator';
  } finally {
    saving.value = false;
  }
}

async function updateAdjudicator() {
  if (!editingAdjudicator.value) return;
  
  saving.value = true;
  error.value = null;
  
  try {
    const updateData: AdjudicatorUpdateRequest = {
      name: form.value.name,
      email: form.value.email || undefined,
      phone: form.value.phone || undefined,
      credential: form.value.credential || undefined,
      organization: form.value.organization || undefined,
      school_affiliation_id: form.value.school_affiliation_id || undefined
    };
    
    const res = await authStore.authFetch(`${API_BASE}/adjudicators/${editingAdjudicator.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(updateData)
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to update adjudicator');
    }
    
    await fetchAdjudicators();
    await fetchCapacity();
    editingAdjudicator.value = null;
    showAddModal.value = false;
    resetForm();
    successMessage.value = 'Adjudicator updated!';
    setTimeout(() => { successMessage.value = null; }, 3000);
  } catch (err: any) {
    error.value = err.message || 'Failed to update adjudicator';
  } finally {
    saving.value = false;
  }
}

async function deleteAdjudicator(adj: FeisAdjudicator) {
  if (!confirm(`Remove ${adj.name} from the roster?`)) return;
  
  try {
    const res = await authStore.authFetch(`${API_BASE}/adjudicators/${adj.id}`, {
      method: 'DELETE'
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to remove adjudicator');
    }
    
    await fetchAdjudicators();
    await fetchCapacity();
    successMessage.value = 'Adjudicator removed from roster';
    setTimeout(() => { successMessage.value = null; }, 3000);
  } catch (err: any) {
    error.value = err.message || 'Failed to remove adjudicator';
  }
}

// Invite functions
async function sendInvite(adj: FeisAdjudicator) {
  try {
    const res = await authStore.authFetch(`${API_BASE}/adjudicators/${adj.id}/invite`, {
      method: 'POST',
      body: JSON.stringify({ adjudicator_id: adj.id })
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to send invite');
    }
    
    const data = await res.json();
    inviteLink.value = data.invite_link;
    showInviteLinkModal.value = true;
    await fetchAdjudicators();
  } catch (err: any) {
    error.value = err.message || 'Failed to send invite';
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteLink.value);
    successMessage.value = 'Link copied to clipboard!';
    setTimeout(() => { successMessage.value = null; }, 2000);
  } catch (err) {
    error.value = 'Failed to copy link';
  }
}

// PIN functions
async function generatePin(adj: FeisAdjudicator) {
  try {
    const res = await authStore.authFetch(`${API_BASE}/adjudicators/${adj.id}/generate-pin`, {
      method: 'POST'
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to generate PIN');
    }
    
    const data = await res.json();
    generatedPin.value = data.pin;
    pinAdjudicatorName.value = adj.name;
    showPinModal.value = true;
    await fetchAdjudicators();
  } catch (err: any) {
    error.value = err.message || 'Failed to generate PIN';
  }
}

// User search functions
async function searchUsers(query: string) {
  if (query.length < 2) {
    searchResults.value = [];
    showSearchResults.value = false;
    return;
  }
  
  isSearching.value = true;
  try {
    const res = await authStore.authFetch(`${API_BASE}/users?search=${encodeURIComponent(query)}&limit=8`);
    if (res.ok) {
      const users: User[] = await res.json();
      // Filter out users already in the roster
      const existingUserIds = adjudicators.value.map(a => a.user_id).filter(Boolean);
      searchResults.value = users.filter(u => !existingUserIds.includes(u.id));
      showSearchResults.value = true;
    }
  } catch (err) {
    console.error('Failed to search users:', err);
  } finally {
    isSearching.value = false;
  }
}

function handleSearchInput(e: Event) {
  const value = (e.target as HTMLInputElement).value;
  searchQuery.value = value;
  form.value.name = value;
  selectedUser.value = null;
  form.value.user_id = '';
  
  // Debounce the search
  if (searchTimeout) clearTimeout(searchTimeout);
  searchTimeout = window.setTimeout(() => {
    searchUsers(value);
  }, 300);
}

function handleSearchBlur() {
  // Delay hiding results to allow clicking on search results
  window.setTimeout(() => {
    showSearchResults.value = false;
  }, 200);
}

function selectUser(user: User) {
  selectedUser.value = user;
  form.value.name = user.name;
  form.value.email = user.email;
  form.value.user_id = user.id;
  searchQuery.value = user.name;
  showSearchResults.value = false;
  searchResults.value = [];
}

function clearSelectedUser() {
  selectedUser.value = null;
  form.value.user_id = '';
  form.value.name = '';
  form.value.email = '';
  searchQuery.value = '';
}

// Helper functions
function resetForm() {
  form.value = {
    name: '',
    email: '',
    phone: '',
    credential: '',
    organization: '',
    school_affiliation_id: '',
    user_id: ''
  };
  searchQuery.value = '';
  searchResults.value = [];
  selectedUser.value = null;
  showSearchResults.value = false;
}

function startEdit(adj: FeisAdjudicator) {
  editingAdjudicator.value = adj;
  form.value = {
    name: adj.name,
    email: adj.email || '',
    phone: adj.phone || '',
    credential: adj.credential || '',
    organization: adj.organization || '',
    school_affiliation_id: adj.school_affiliation_id || '',
    user_id: adj.user_id || ''
  };
  showAddModal.value = true;
}

function cancelEdit() {
  editingAdjudicator.value = null;
  showAddModal.value = false;
  resetForm();
}

onMounted(async () => {
  loading.value = true;
  await Promise.all([fetchAdjudicators(), fetchCapacity(), fetchTeachers()]);
  loading.value = false;
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header with close button -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-slate-800">Adjudicator Roster</h2>
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

    <!-- Tabs -->
    <div class="border-b border-slate-200">
      <nav class="flex space-x-8">
        <button
          @click="activeTab = 'judges'"
          class="py-4 px-1 border-b-2 font-medium text-sm transition-colors"
          :class="activeTab === 'judges'
            ? 'border-emerald-600 text-emerald-600'
            : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'"
        >
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Judges
          </div>
        </button>
        <button
          @click="activeTab = 'panels'"
          class="py-4 px-1 border-b-2 font-medium text-sm transition-colors"
          :class="activeTab === 'panels'
            ? 'border-emerald-600 text-emerald-600'
            : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'"
        >
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Panels
          </div>
        </button>
      </nav>
    </div>

    <!-- Messages -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
      <button @click="error = null" class="float-right font-bold">&times;</button>
    </div>
    <div v-if="successMessage" class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
      {{ successMessage }}
    </div>

    <!-- Judges Tab Content -->
    <div v-if="activeTab === 'judges'">
      <!-- Capacity Metrics Card -->
      <div v-if="capacity" class="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl p-6 text-white shadow-lg">
      <div class="flex items-start justify-between">
        <div>
          <h3 class="text-lg font-semibold mb-2">Scheduling Capacity</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
            <div class="text-center">
              <div class="text-3xl font-bold">{{ capacity.total_adjudicators }}</div>
              <div class="text-indigo-200 text-sm">Total</div>
            </div>
            <div class="text-center">
              <div class="text-3xl font-bold">{{ capacity.confirmed_count }}</div>
              <div class="text-indigo-200 text-sm">Confirmed</div>
            </div>
            <div class="text-center">
              <div class="text-3xl font-bold">{{ capacity.max_grade_stages }}</div>
              <div class="text-indigo-200 text-sm">Max Grade Stages</div>
            </div>
            <div class="text-center">
              <div class="text-3xl font-bold">{{ capacity.max_champs_panels }}</div>
              <div class="text-indigo-200 text-sm">Max Champs Panels</div>
            </div>
          </div>
        </div>
        <div class="hidden lg:block max-w-xs text-sm text-indigo-100">
          {{ capacity.recommendation }}
        </div>
      </div>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <span class="text-slate-600">
          <span class="font-medium">{{ totalCount }}</span> adjudicators
          <span v-if="confirmedCount > 0" class="text-green-600">
            ({{ confirmedCount }} confirmed)
          </span>
        </span>
      </div>
      <button
        @click="showAddModal = true; editingAdjudicator = null; resetForm();"
        class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Add Adjudicator
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-emerald-200 border-t-emerald-600"></div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="adjudicators.length === 0"
      class="bg-white rounded-xl shadow-lg border border-slate-200 p-12 text-center"
    >
      <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Adjudicators Yet</h3>
      <p class="text-slate-500 mb-4">Add judges to your roster to start scheduling.</p>
      <button
        @click="showAddModal = true"
        class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700"
      >
        Add Your First Adjudicator
      </button>
    </div>

    <!-- Adjudicator List -->
    <div v-else class="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      <table class="min-w-full divide-y divide-slate-200">
        <thead class="bg-slate-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Credential</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">School</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Access</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-slate-200">
          <tr v-for="adj in adjudicators" :key="adj.id" class="hover:bg-slate-50">
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="flex items-center">
                <div>
                  <div class="text-sm font-medium text-slate-900">{{ adj.name }}</div>
                  <div v-if="adj.email" class="text-sm text-slate-500">{{ adj.email }}</div>
                </div>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="text-sm text-slate-900">{{ adj.credential || '-' }}</div>
              <div v-if="adj.organization" class="text-sm text-slate-500">{{ adj.organization }}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span class="text-sm text-slate-600">{{ adj.school_affiliation_name || '-' }}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span 
                :class="[getAdjudicatorStatusBadge(adj.status).color, 'px-2 py-1 text-xs font-medium rounded-full']"
              >
                {{ getAdjudicatorStatusBadge(adj.status).label }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
              <div class="flex items-center gap-2">
                <span v-if="adj.user_id" class="text-green-600" title="Account linked">
                  <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                  </svg>
                </span>
                <span v-if="adj.has_access_pin" class="text-amber-600" title="PIN set">
                  <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd" />
                  </svg>
                </span>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
              <div class="flex items-center justify-end gap-2">
                <!-- Send invite link - only for users WITHOUT existing account who have email -->
                <button
                  v-if="adj.email && !adj.user_id"
                  @click="sendInvite(adj)"
                  class="text-indigo-600 hover:text-indigo-900"
                  title="Send invite link"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </button>
                <!-- Generate PIN - only for users WITHOUT existing account -->
                <button
                  v-if="!adj.user_id"
                  @click="generatePin(adj)"
                  class="text-amber-600 hover:text-amber-900"
                  title="Generate day-of PIN"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                  </svg>
                </button>
                <!-- Edit -->
                <button
                  @click="startEdit(adj)"
                  class="text-slate-600 hover:text-slate-900"
                  title="Edit"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <!-- Remove -->
                <button
                  @click="deleteAdjudicator(adj)"
                  class="text-red-600 hover:text-red-900"
                  title="Remove"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    </div>

    <!-- Panels Tab Content -->
    <div v-if="activeTab === 'panels'">
      <PanelsManager :feis-id="feisId" :feis-name="feisName" />
    </div>

    <!-- Add/Edit Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div class="p-6 border-b border-slate-200">
          <h3 class="text-xl font-bold text-slate-800">
            {{ editingAdjudicator ? 'Edit Adjudicator' : 'Add Adjudicator' }}
          </h3>
        </div>
        
        <form @submit.prevent="editingAdjudicator ? updateAdjudicator() : createAdjudicator()" class="p-6 space-y-4">
          <!-- Name with Typeahead Search -->
          <div class="relative">
            <label class="block text-sm font-medium text-slate-700 mb-1">Name *</label>
            
            <!-- Selected User Badge -->
            <div v-if="selectedUser && !editingAdjudicator" class="mb-2">
              <div class="flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                <svg class="w-5 h-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
                <div class="flex-1">
                  <span class="font-medium text-emerald-800">{{ selectedUser.name }}</span>
                  <span class="text-emerald-600 text-sm ml-2">{{ selectedUser.email }}</span>
                </div>
                <button
                  type="button"
                  @click="clearSelectedUser"
                  class="text-emerald-600 hover:text-emerald-800"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <p class="mt-1 text-sm text-emerald-600">
                ✓ Existing account — no invite needed, they can log in directly
              </p>
            </div>
            
            <!-- Search Input -->
            <div v-if="!selectedUser || editingAdjudicator" class="relative">
              <input
                :value="editingAdjudicator ? form.name : searchQuery"
                @input="editingAdjudicator ? (form.name = ($event.target as HTMLInputElement).value) : handleSearchInput($event)"
                @focus="!editingAdjudicator && searchQuery.length >= 2 && (showSearchResults = true)"
                @blur="handleSearchBlur"
                type="text"
                placeholder="Start typing to search existing users..."
                class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                required
              />
              
              <!-- Search indicator -->
              <div v-if="isSearching" class="absolute right-3 top-1/2 -translate-y-1/2">
                <div class="animate-spin rounded-full h-4 w-4 border-2 border-slate-300 border-t-emerald-600"></div>
              </div>
              
              <!-- Search Results Dropdown -->
              <div
                v-if="showSearchResults && searchResults.length > 0 && !editingAdjudicator"
                class="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
              >
                <button
                  v-for="user in searchResults"
                  :key="user.id"
                  type="button"
                  @mousedown.prevent="selectUser(user)"
                  class="w-full px-4 py-3 text-left hover:bg-emerald-50 flex items-center gap-3 border-b border-slate-100 last:border-0"
                >
                  <div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                    <span class="text-emerald-700 font-medium text-sm">{{ user.name.charAt(0).toUpperCase() }}</span>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="font-medium text-slate-800 truncate">{{ user.name }}</div>
                    <div class="text-sm text-slate-500 truncate">{{ user.email }}</div>
                  </div>
                  <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
                    Has account
                  </span>
                </button>
              </div>
              
              <!-- No results message -->
              <div
                v-if="showSearchResults && searchResults.length === 0 && searchQuery.length >= 2 && !isSearching && !editingAdjudicator"
                class="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg p-4 text-center"
              >
                <p class="text-slate-600 text-sm mb-2">No existing user found for "{{ searchQuery }}"</p>
                <p class="text-slate-500 text-xs">Continue filling out the form to add them as a new adjudicator</p>
              </div>
            </div>
            
            <p v-if="!selectedUser && !editingAdjudicator" class="mt-1 text-sm text-slate-500">
              Type 2+ characters to search existing users, or enter a new name
            </p>
          </div>
          
          <!-- Email -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input
              v-model="form.email"
              type="email"
              placeholder="judge@example.com"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              :disabled="!!selectedUser"
              :class="{ 'bg-slate-50': !!selectedUser }"
            />
            <p v-if="!selectedUser" class="mt-1 text-sm text-slate-500">Required to send an invite link</p>
            <p v-else class="mt-1 text-sm text-emerald-600">Email from existing account</p>
          </div>
          
          <!-- Phone -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Phone</label>
            <input
              v-model="form.phone"
              type="tel"
              placeholder="+1 555 123 4567"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
          
          <!-- Credential -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Credential</label>
            <select
              v-model="form.credential"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">Select credential...</option>
              <option v-for="cred in ADJUDICATOR_CREDENTIALS" :key="cred.value" :value="cred.value">
                {{ cred.label }}
              </option>
            </select>
          </div>
          
          <!-- Organization -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Organization</label>
            <select
              v-model="form.organization"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">Select organization...</option>
              <option v-for="org in DANCE_ORGANIZATIONS" :key="org.value" :value="org.value">
                {{ org.label }}
              </option>
            </select>
          </div>
          
          <!-- School Affiliation -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">School Affiliation</label>
            <select
              v-model="form.school_affiliation_id"
              class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">None (no school conflict detection)</option>
              <option v-for="teacher in teachers" :key="teacher.id" :value="teacher.id">
                {{ teacher.name }}
              </option>
            </select>
            <p class="mt-1 text-sm text-slate-500">Used to detect conflicts when judging own students</p>
          </div>
          
          <!-- Buttons -->
          <div class="flex gap-3 pt-4">
            <button
              type="submit"
              :disabled="!isFormValid || saving"
              class="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
            >
              {{ saving ? 'Saving...' : (editingAdjudicator ? 'Save Changes' : 'Add to Roster') }}
            </button>
            <button
              type="button"
              @click="cancelEdit"
              class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Invite Link Modal -->
    <div v-if="showInviteLinkModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
        <h3 class="text-xl font-bold text-slate-800 mb-4">Invite Link Generated</h3>
        <p class="text-slate-600 mb-4">Share this link with the adjudicator to accept the invitation:</p>
        
        <div class="bg-slate-100 rounded-lg p-4 mb-4">
          <code class="text-sm break-all text-slate-700">{{ inviteLink }}</code>
        </div>
        
        <div class="flex gap-3">
          <button
            @click="copyInviteLink"
            class="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700"
          >
            Copy Link
          </button>
          <button
            @click="showInviteLinkModal = false"
            class="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>

    <!-- PIN Modal -->
    <div v-if="showPinModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 text-center">
        <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </div>
        
        <h3 class="text-xl font-bold text-slate-800 mb-2">Day-of Access PIN</h3>
        <p class="text-slate-600 mb-4">PIN for <strong>{{ pinAdjudicatorName }}</strong></p>
        
        <div class="bg-slate-900 rounded-lg p-6 mb-4">
          <div class="text-4xl font-mono font-bold text-amber-400 tracking-widest">
            {{ generatedPin }}
          </div>
        </div>
        
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-left">
          <p class="text-amber-800 text-sm">
            <strong>Important:</strong> This PIN will not be shown again. Write it down or share it directly with the adjudicator.
          </p>
        </div>
        
        <button
          @click="showPinModal = false; generatedPin = ''"
          class="w-full px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300"
        >
          I've Saved the PIN
        </button>
      </div>
    </div>
  </div>
</template>

