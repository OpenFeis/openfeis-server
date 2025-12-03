<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { Dancer, CompetitionLevel, Gender } from '../../models/types';

const auth = useAuthStore();

// Profile editing
const isEditingProfile = ref(false);
const editName = ref('');
const profileLoading = ref(false);
const profileError = ref<string | null>(null);
const profileSuccess = ref<string | null>(null);

// Password change
const showPasswordChange = ref(false);
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const passwordLoading = ref(false);
const passwordError = ref<string | null>(null);
const passwordSuccess = ref<string | null>(null);

// Dancers
const dancers = ref<Dancer[]>([]);
const dancersLoading = ref(false);
const dancersError = ref<string | null>(null);
const editingDancer = ref<Dancer | null>(null);
const showDancerModal = ref(false);
const dancerModalMode = ref<'add' | 'edit'>('add');
const dancerForm = ref({
  name: '',
  dob: '',
  gender: 'female' as Gender,
  current_level: 'beginner' as CompetitionLevel,
  clrg_number: ''
});
const dancerSaving = ref(false);
const dancerError = ref<string | null>(null);

// Registration history
interface RegistrationEntry {
  id: string;
  dancer_id: string;
  dancer_name: string;
  competition_id: string;
  competition_name: string;
  competitor_number?: number;
  paid: boolean;
  pay_later: boolean;
}
const registrations = ref<RegistrationEntry[]>([]);
const registrationsLoading = ref(false);

// Level and gender options
const levelOptions: { value: CompetitionLevel; label: string }[] = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'novice', label: 'Novice' },
  { value: 'prizewinner', label: 'Prizewinner' },
  { value: 'championship', label: 'Championship' },
];

const genderOptions: { value: Gender; label: string }[] = [
  { value: 'female', label: 'Girl' },
  { value: 'male', label: 'Boy' },
  { value: 'other', label: 'Other' },
];

// Fetch data on mount
onMounted(async () => {
  await Promise.all([
    fetchDancers(),
    fetchRegistrations()
  ]);
});

// Profile methods
const startEditProfile = () => {
  editName.value = auth.user?.name || '';
  isEditingProfile.value = true;
  profileError.value = null;
  profileSuccess.value = null;
};

const cancelEditProfile = () => {
  isEditingProfile.value = false;
  profileError.value = null;
};

const saveProfile = async () => {
  if (!editName.value.trim()) {
    profileError.value = 'Name is required';
    return;
  }
  
  profileLoading.value = true;
  profileError.value = null;
  profileSuccess.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/auth/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editName.value.trim() })
    });
    
    if (response.ok) {
      const updated = await response.json();
      // Update the auth store
      if (auth.user) {
        auth.user.name = updated.name;
      }
      isEditingProfile.value = false;
      profileSuccess.value = 'Profile updated successfully';
      setTimeout(() => profileSuccess.value = null, 3000);
    } else {
      const error = await response.json();
      profileError.value = error.detail || 'Failed to update profile';
    }
  } catch (error) {
    profileError.value = 'Network error. Please try again.';
  } finally {
    profileLoading.value = false;
  }
};

// Password methods
const openPasswordChange = () => {
  showPasswordChange.value = true;
  currentPassword.value = '';
  newPassword.value = '';
  confirmPassword.value = '';
  passwordError.value = null;
  passwordSuccess.value = null;
};

const closePasswordChange = () => {
  showPasswordChange.value = false;
  passwordError.value = null;
};

const changePassword = async () => {
  // Validation
  if (!currentPassword.value) {
    passwordError.value = 'Current password is required';
    return;
  }
  if (newPassword.value.length < 6) {
    passwordError.value = 'New password must be at least 6 characters';
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'Passwords do not match';
    return;
  }
  
  passwordLoading.value = true;
  passwordError.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/auth/password', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value
      })
    });
    
    if (response.ok) {
      passwordSuccess.value = 'Password changed successfully';
      showPasswordChange.value = false;
      setTimeout(() => passwordSuccess.value = null, 3000);
    } else {
      const error = await response.json();
      passwordError.value = error.detail || 'Failed to change password';
    }
  } catch (error) {
    passwordError.value = 'Network error. Please try again.';
  } finally {
    passwordLoading.value = false;
  }
};

// Dancer methods
const fetchDancers = async () => {
  dancersLoading.value = true;
  dancersError.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/dancers/mine');
    if (response.ok) {
      dancers.value = await response.json();
    } else {
      dancersError.value = 'Failed to load dancers';
    }
  } catch (error) {
    dancersError.value = 'Network error loading dancers';
  } finally {
    dancersLoading.value = false;
  }
};

const openAddDancer = () => {
  dancerModalMode.value = 'add';
  dancerForm.value = {
    name: '',
    dob: '',
    gender: 'female',
    current_level: 'beginner',
    clrg_number: ''
  };
  dancerError.value = null;
  showDancerModal.value = true;
};

const openEditDancer = (dancer: Dancer) => {
  dancerModalMode.value = 'edit';
  editingDancer.value = dancer;
  dancerForm.value = {
    name: dancer.name,
    dob: dancer.dob,
    gender: dancer.gender,
    current_level: dancer.current_level,
    clrg_number: dancer.clrg_number || ''
  };
  dancerError.value = null;
  showDancerModal.value = true;
};

const closeDancerModal = () => {
  showDancerModal.value = false;
  editingDancer.value = null;
  dancerError.value = null;
};

const saveDancer = async () => {
  // Validation
  if (!dancerForm.value.name.trim()) {
    dancerError.value = 'Name is required';
    return;
  }
  if (!dancerForm.value.dob) {
    dancerError.value = 'Date of birth is required';
    return;
  }
  
  dancerSaving.value = true;
  dancerError.value = null;
  
  try {
    const url = dancerModalMode.value === 'add' 
      ? '/api/v1/dancers'
      : `/api/v1/dancers/${editingDancer.value?.id}`;
    
    const method = dancerModalMode.value === 'add' ? 'POST' : 'PUT';
    
    const response = await auth.authFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: dancerForm.value.name.trim(),
        dob: dancerForm.value.dob,
        gender: dancerForm.value.gender,
        current_level: dancerForm.value.current_level,
        clrg_number: dancerForm.value.clrg_number || null
      })
    });
    
    if (response.ok) {
      await fetchDancers();
      closeDancerModal();
    } else {
      const error = await response.json();
      dancerError.value = error.detail || 'Failed to save dancer';
    }
  } catch (error) {
    dancerError.value = 'Network error. Please try again.';
  } finally {
    dancerSaving.value = false;
  }
};

const deleteDancer = async (dancer: Dancer) => {
  if (!confirm(`Are you sure you want to delete ${dancer.name}? This cannot be undone.`)) {
    return;
  }
  
  try {
    const response = await auth.authFetch(`/api/v1/dancers/${dancer.id}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      await fetchDancers();
    } else {
      const error = await response.json();
      alert(error.detail || 'Failed to delete dancer');
    }
  } catch (error) {
    alert('Network error. Please try again.');
  }
};

// Registration history methods
const fetchRegistrations = async () => {
  registrationsLoading.value = true;
  
  try {
    const response = await auth.authFetch('/api/v1/me/entries');
    if (response.ok) {
      registrations.value = await response.json();
    }
  } catch (error) {
    console.error('Failed to fetch registrations:', error);
  } finally {
    registrationsLoading.value = false;
  }
};

// Computed: competition age for a dancer
const getCompetitionAge = (dob: string): number => {
  const birthDate = new Date(dob);
  const jan1 = new Date(new Date().getFullYear(), 0, 1);
  let age = jan1.getFullYear() - birthDate.getFullYear();
  const monthDiff = jan1.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && jan1.getDate() < birthDate.getDate())) {
    age--;
  }
  return age;
};

// Group registrations by dancer
const registrationsByDancer = computed(() => {
  const grouped: Record<string, { dancer_name: string; entries: RegistrationEntry[] }> = {};
  for (const entry of registrations.value) {
    if (!grouped[entry.dancer_id]) {
      grouped[entry.dancer_id] = { dancer_name: entry.dancer_name, entries: [] };
    }
    const group = grouped[entry.dancer_id];
    if (group) {
      group.entries.push(entry);
    }
  }
  return grouped;
});
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <!-- Page Header -->
    <div>
      <h1 class="text-3xl font-bold text-slate-800">My Account</h1>
      <p class="text-slate-600 mt-1">Manage your profile, dancers, and registrations</p>
    </div>

    <!-- Profile Section -->
    <section class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div class="bg-gradient-to-r from-slate-700 to-slate-800 px-6 py-4">
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          Profile
        </h2>
      </div>
      
      <div class="p-6 space-y-4">
        <!-- Success message -->
        <div v-if="profileSuccess" class="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-2">
          <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <span class="text-emerald-700 text-sm font-medium">{{ profileSuccess }}</span>
        </div>

        <!-- Password success message -->
        <div v-if="passwordSuccess" class="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-2">
          <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <span class="text-emerald-700 text-sm font-medium">{{ passwordSuccess }}</span>
        </div>
        
        <!-- View Mode -->
        <div v-if="!isEditingProfile" class="space-y-4">
          <div class="grid sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Name</label>
              <p class="text-slate-800 font-medium">{{ auth.user?.name }}</p>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Email</label>
              <div class="flex items-center gap-2">
                <p class="text-slate-800 font-medium">{{ auth.user?.email }}</p>
                <span 
                  v-if="auth.user?.email_verified"
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700"
                >
                  <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                  </svg>
                  Verified
                </span>
                <span 
                  v-else
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700"
                >
                  Unverified
                </span>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Role</label>
              <p class="text-slate-800 font-medium capitalize">{{ auth.user?.role?.replace('_', ' ') }}</p>
            </div>
          </div>
          
          <div class="flex gap-3 pt-2">
            <button
              @click="startEditProfile"
              class="px-4 py-2 rounded-lg font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
            >
              Edit Name
            </button>
            <button
              @click="openPasswordChange"
              class="px-4 py-2 rounded-lg font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
            >
              Change Password
            </button>
          </div>
        </div>
        
        <!-- Edit Mode -->
        <div v-else class="space-y-4">
          <div v-if="profileError" class="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-sm">
            {{ profileError }}
          </div>
          
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">Name</label>
            <input
              v-model="editName"
              type="text"
              class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
              placeholder="Your name"
            />
          </div>
          
          <div class="flex gap-3">
            <button
              @click="saveProfile"
              :disabled="profileLoading"
              class="px-4 py-2 rounded-lg font-medium bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
            >
              {{ profileLoading ? 'Saving...' : 'Save Changes' }}
            </button>
            <button
              @click="cancelEditProfile"
              class="px-4 py-2 rounded-lg font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Password Change Modal -->
    <Teleport to="body">
      <div v-if="showPasswordChange" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/50" @click="closePasswordChange"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
          <div class="bg-gradient-to-r from-slate-700 to-slate-800 px-6 py-4 flex justify-between items-center">
            <h3 class="text-lg font-bold text-white">Change Password</h3>
            <button @click="closePasswordChange" class="text-white/70 hover:text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div class="p-6 space-y-4">
            <div v-if="passwordError" class="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-sm">
              {{ passwordError }}
            </div>
            
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Current Password</label>
              <input
                v-model="currentPassword"
                type="password"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">New Password</label>
              <input
                v-model="newPassword"
                type="password"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
              />
              <p class="text-xs text-slate-500 mt-1">At least 6 characters</p>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">Confirm New Password</label>
              <input
                v-model="confirmPassword"
                type="password"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
              />
            </div>
            
            <div class="flex gap-3 pt-2">
              <button
                @click="changePassword"
                :disabled="passwordLoading"
                class="flex-1 py-2 rounded-xl font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
              >
                {{ passwordLoading ? 'Changing...' : 'Change Password' }}
              </button>
              <button
                @click="closePasswordChange"
                class="flex-1 py-2 rounded-xl font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- My Dancers Section -->
    <section class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4 flex justify-between items-center">
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          My Dancers
        </h2>
        <button
          @click="openAddDancer"
          class="px-4 py-2 rounded-lg font-medium bg-white/20 text-white hover:bg-white/30 transition-colors flex items-center gap-1"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Dancer
        </button>
      </div>
      
      <div class="p-6">
        <!-- Loading -->
        <div v-if="dancersLoading" class="flex items-center justify-center py-8">
          <div class="animate-spin rounded-full h-8 w-8 border-4 border-emerald-200 border-t-emerald-600"></div>
        </div>
        
        <!-- Error -->
        <div v-else-if="dancersError" class="text-center py-8">
          <p class="text-red-600">{{ dancersError }}</p>
          <button @click="fetchDancers" class="mt-2 text-emerald-600 hover:text-emerald-700 font-medium">
            Try Again
          </button>
        </div>
        
        <!-- Empty State -->
        <div v-else-if="dancers.length === 0" class="text-center py-12">
          <div class="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-700 mb-2">No Dancers Yet</h3>
          <p class="text-slate-500 text-sm mb-4">Add your dancers to easily register them for competitions.</p>
          <button
            @click="openAddDancer"
            class="px-6 py-2 rounded-xl font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
          >
            Add Your First Dancer
          </button>
        </div>
        
        <!-- Dancer List -->
        <div v-else class="space-y-4">
          <div
            v-for="dancer in dancers"
            :key="dancer.id"
            class="border border-slate-200 rounded-xl p-4 hover:border-emerald-300 transition-colors"
          >
            <div class="flex items-start justify-between">
              <div>
                <h3 class="font-bold text-slate-800 text-lg">{{ dancer.name }}</h3>
                <div class="flex flex-wrap gap-2 mt-2">
                  <span class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium bg-amber-100 text-amber-800">
                    Age {{ getCompetitionAge(dancer.dob) }} (U{{ getCompetitionAge(dancer.dob) + 1 }})
                  </span>
                  <span class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium bg-indigo-100 text-indigo-800 capitalize">
                    {{ dancer.current_level }}
                  </span>
                  <span class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 capitalize">
                    {{ dancer.gender === 'female' ? 'Girl' : dancer.gender === 'male' ? 'Boy' : 'Other' }}
                  </span>
                  <span v-if="dancer.clrg_number" class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium bg-emerald-100 text-emerald-800">
                    CLRG #{{ dancer.clrg_number }}
                  </span>
                </div>
                <p class="text-xs text-slate-500 mt-2">
                  DOB: {{ new Date(dancer.dob).toLocaleDateString() }}
                </p>
              </div>
              <div class="flex gap-2">
                <button
                  @click="openEditDancer(dancer)"
                  class="p-2 rounded-lg text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                  title="Edit"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  @click="deleteDancer(dancer)"
                  class="p-2 rounded-lg text-slate-500 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Delete"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Dancer Add/Edit Modal -->
    <Teleport to="body">
      <div v-if="showDancerModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/50" @click="closeDancerModal"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[90vh] overflow-y-auto">
          <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4 flex justify-between items-center sticky top-0">
            <h3 class="text-lg font-bold text-white">
              {{ dancerModalMode === 'add' ? 'Add Dancer' : 'Edit Dancer' }}
            </h3>
            <button @click="closeDancerModal" class="text-white/70 hover:text-white">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div class="p-6 space-y-4">
            <div v-if="dancerError" class="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-sm">
              {{ dancerError }}
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-1">Dancer's Full Name</label>
              <input
                v-model="dancerForm.name"
                type="text"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
                placeholder="e.g., Saoirse O'Brien"
              />
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-1">Date of Birth</label>
              <input
                v-model="dancerForm.dob"
                type="date"
                :max="new Date().toISOString().split('T')[0]"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
              />
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Category</label>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="option in genderOptions"
                  :key="option.value"
                  type="button"
                  @click="dancerForm.gender = option.value"
                  :class="[
                    'px-4 py-2 rounded-xl font-medium transition-all border-2',
                    dancerForm.gender === option.value
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-300'
                  ]"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Current Level</label>
              <div class="space-y-2">
                <button
                  v-for="option in levelOptions"
                  :key="option.value"
                  type="button"
                  @click="dancerForm.current_level = option.value"
                  :class="[
                    'w-full px-4 py-2 rounded-xl text-left transition-all border-2',
                    dancerForm.current_level === option.value
                      ? 'bg-emerald-50 border-emerald-500'
                      : 'bg-white border-slate-200 hover:border-emerald-300'
                  ]"
                >
                  <span :class="[
                    'font-medium',
                    dancerForm.current_level === option.value ? 'text-emerald-700' : 'text-slate-700'
                  ]">
                    {{ option.label }}
                  </span>
                </button>
              </div>
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-1">
                CLRG Number
                <span class="text-slate-400 font-normal">(Optional)</span>
              </label>
              <input
                v-model="dancerForm.clrg_number"
                type="text"
                class="w-full px-4 py-2 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
                placeholder="e.g., 12345"
              />
            </div>
            
            <div class="flex gap-3 pt-4">
              <button
                @click="saveDancer"
                :disabled="dancerSaving"
                class="flex-1 py-3 rounded-xl font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
              >
                {{ dancerSaving ? 'Saving...' : (dancerModalMode === 'add' ? 'Add Dancer' : 'Save Changes') }}
              </button>
              <button
                @click="closeDancerModal"
                class="flex-1 py-3 rounded-xl font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Registration History Section -->
    <section class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-4">
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          Registration History
        </h2>
      </div>
      
      <div class="p-6">
        <!-- Loading -->
        <div v-if="registrationsLoading" class="flex items-center justify-center py-8">
          <div class="animate-spin rounded-full h-8 w-8 border-4 border-violet-200 border-t-violet-600"></div>
        </div>
        
        <!-- Empty State -->
        <div v-else-if="registrations.length === 0" class="text-center py-12">
          <div class="w-16 h-16 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-700 mb-2">No Registrations Yet</h3>
          <p class="text-slate-500 text-sm">Your registration history will appear here after you register for competitions.</p>
        </div>
        
        <!-- Registration List by Dancer -->
        <div v-else class="space-y-6">
          <div
            v-for="(group, dancerId) in registrationsByDancer"
            :key="dancerId"
            class="border border-slate-200 rounded-xl overflow-hidden"
          >
            <div class="bg-slate-50 px-4 py-2 border-b border-slate-200">
              <h4 class="font-semibold text-slate-800">{{ group.dancer_name }}</h4>
              <p class="text-xs text-slate-500">{{ group.entries.length }} registration(s)</p>
            </div>
            <div class="divide-y divide-slate-100">
              <div
                v-for="entry in group.entries"
                :key="entry.id"
                class="px-4 py-3 flex items-center justify-between"
              >
                <div>
                  <p class="font-medium text-slate-700 text-sm">{{ entry.competition_name }}</p>
                  <div class="flex gap-2 mt-1">
                    <span 
                      v-if="entry.competitor_number"
                      class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-700"
                    >
                      #{{ entry.competitor_number }}
                    </span>
                    <span 
                      :class="[
                        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                        entry.paid 
                          ? 'bg-emerald-100 text-emerald-700'
                          : entry.pay_later 
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-red-100 text-red-700'
                      ]"
                    >
                      {{ entry.paid ? 'Paid' : (entry.pay_later ? 'Pay at Door' : 'Unpaid') }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

