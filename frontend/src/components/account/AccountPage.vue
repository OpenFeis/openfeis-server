<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { Dancer, CompetitionLevel, Gender, User } from '../../models/types';

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
  current_level: 'beginner_1' as CompetitionLevel,
  clrg_number: '',
  school_id: '',
  is_adult: false,
  // Per-dance levels
  level_reel: null as CompetitionLevel | null,
  level_light_jig: null as CompetitionLevel | null,
  level_slip_jig: null as CompetitionLevel | null,
  level_single_jig: null as CompetitionLevel | null,
  level_treble_jig: null as CompetitionLevel | null,
  level_hornpipe: null as CompetitionLevel | null,
  level_traditional_set: null as CompetitionLevel | null,
  level_figure: null as CompetitionLevel | null,
});

// Per-dance levels UI toggle
const showPerDanceLevels = ref(false);
const dancerSaving = ref(false);
const dancerError = ref<string | null>(null);

// Teacher/School selection
const teachers = ref<User[]>([]);
const teacherSearch = ref('');
const teachersLoading = ref(false);
const showTeacherDropdown = ref(false);
const selectedTeacher = ref<User | null>(null);

// Fetch teachers
const fetchTeachers = async (search?: string) => {
  teachersLoading.value = true;
  try {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    
    const response = await fetch(`/api/v1/teachers?${params.toString()}`);
    if (response.ok) {
      teachers.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch teachers:', e);
  } finally {
    teachersLoading.value = false;
  }
};

// Teacher search debounce
let teacherSearchTimeout: number | null = null;
const onTeacherSearchInput = () => {
  if (teacherSearchTimeout) clearTimeout(teacherSearchTimeout);
  teacherSearchTimeout = window.setTimeout(() => {
    fetchTeachers(teacherSearch.value);
  }, 300);
};

// Select a teacher
const selectTeacher = (teacher: User) => {
  selectedTeacher.value = teacher;
  dancerForm.value.school_id = teacher.id;
  teacherSearch.value = teacher.name;
  showTeacherDropdown.value = false;
};

// Clear teacher selection
const clearTeacher = () => {
  selectedTeacher.value = null;
  dancerForm.value.school_id = '';
  teacherSearch.value = '';
};

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
const showRegistrationHistory = ref(false);

// Results/Placements
interface PlacementResult {
  id: string;
  dancer_id: string;
  dancer_name: string;
  competition_id: string;
  competition_name: string;
  feis_id: string;
  feis_name: string;
  rank: number;
  irish_points: number;
  dance_type?: string;
  level: string;
  competition_date: string;
}

interface DancerResults {
  dancer_id: string;
  dancer_name: string;
  placements: PlacementResult[];
}

const allResults = ref<DancerResults[]>([]);
const resultsLoading = ref(false);
const expandedResults = ref<Set<string>>(new Set());

const toggleResultExpansion = (resultId: string) => {
  if (expandedResults.value.has(resultId)) {
    expandedResults.value.delete(resultId);
  } else {
    expandedResults.value.add(resultId);
  }
};

// Level and gender options
const levelOptions: { value: CompetitionLevel; label: string }[] = [
  { value: 'first_feis', label: 'First Feis' },
  { value: 'beginner_1', label: 'Beginner 1' },
  { value: 'beginner_2', label: 'Beginner 2' },
  { value: 'novice', label: 'Novice' },
  { value: 'prizewinner', label: 'Prizewinner' },
  { value: 'preliminary_championship', label: 'Prelim Champ' },
  { value: 'open_championship', label: 'Open Champ' },
];

const genderOptions: { value: Gender; label: string }[] = [
  { value: 'female', label: 'Girl' },
  { value: 'male', label: 'Boy' },
  { value: 'other', label: 'Other' },
];

// Fetch results for all dancers
const fetchResults = async () => {
  resultsLoading.value = true;
  
  try {
    // First fetch dancers to get their IDs
    await fetchDancers();
    
    // Then fetch placements for each dancer
    const resultsPromises = dancers.value.map(async (dancer) => {
      try {
        const response = await auth.authFetch(`/api/v1/dancers/${dancer.id}/placements`);
        if (response.ok) {
          const data = await response.json();
          return {
            dancer_id: dancer.id,
            dancer_name: dancer.name,
            placements: data.placements || []
          };
        }
      } catch (e) {
        console.error(`Failed to fetch results for ${dancer.name}:`, e);
      }
      return {
        dancer_id: dancer.id,
        dancer_name: dancer.name,
        placements: []
      };
    });
    
    allResults.value = await Promise.all(resultsPromises);
  } catch (error) {
    console.error('Failed to fetch results:', error);
  } finally {
    resultsLoading.value = false;
  }
};

// Fetch data on mount
onMounted(async () => {
  await Promise.all([
    fetchDancers(),
    fetchResults(),
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

const openAddDancer = async () => {
  dancerModalMode.value = 'add';
  dancerForm.value = {
    name: '',
    dob: '',
    gender: 'female',
    current_level: 'beginner_1',
    clrg_number: '',
    school_id: '',
    is_adult: false,
    level_reel: null,
    level_light_jig: null,
    level_slip_jig: null,
    level_single_jig: null,
    level_treble_jig: null,
    level_hornpipe: null,
    level_traditional_set: null,
    level_figure: null,
  };
  // Reset teacher selection
  selectedTeacher.value = null;
  teacherSearch.value = '';
  showPerDanceLevels.value = false;
  dancerError.value = null;
  showDancerModal.value = true;
  // Fetch teachers for dropdown
  await fetchTeachers();
};

const openEditDancer = async (dancer: Dancer) => {
  dancerModalMode.value = 'edit';
  editingDancer.value = dancer;
  dancerForm.value = {
    name: dancer.name,
    dob: dancer.dob,
    gender: dancer.gender,
    current_level: dancer.current_level,
    clrg_number: dancer.clrg_number || '',
    school_id: dancer.school_id || '',
    is_adult: dancer.is_adult || false,
    level_reel: dancer.level_reel || null,
    level_light_jig: dancer.level_light_jig || null,
    level_slip_jig: dancer.level_slip_jig || null,
    level_single_jig: dancer.level_single_jig || null,
    level_treble_jig: dancer.level_treble_jig || null,
    level_hornpipe: dancer.level_hornpipe || null,
    level_traditional_set: dancer.level_traditional_set || null,
    level_figure: dancer.level_figure || null,
  };
  // Show per-dance levels section if any are set
  showPerDanceLevels.value = !!(dancer.level_reel || dancer.level_light_jig || dancer.level_slip_jig ||
    dancer.level_single_jig || dancer.level_treble_jig || dancer.level_hornpipe ||
    dancer.level_traditional_set || dancer.level_figure);
  // Reset teacher selection
  selectedTeacher.value = null;
  teacherSearch.value = '';
  dancerError.value = null;
  showDancerModal.value = true;
  // Fetch teachers for dropdown
  await fetchTeachers();
  // If dancer has a school, try to find and display it
  if (dancer.school_id) {
    const teacher = teachers.value.find(t => t.id === dancer.school_id);
    if (teacher) {
      selectedTeacher.value = teacher;
      teacherSearch.value = teacher.name;
    }
  }
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
        clrg_number: dancerForm.value.clrg_number || null,
        school_id: dancerForm.value.school_id || null,
        is_adult: dancerForm.value.is_adult,
        // Per-dance levels
        level_reel: dancerForm.value.level_reel,
        level_light_jig: dancerForm.value.level_light_jig,
        level_slip_jig: dancerForm.value.level_slip_jig,
        level_single_jig: dancerForm.value.level_single_jig,
        level_treble_jig: dancerForm.value.level_treble_jig,
        level_hornpipe: dancerForm.value.level_hornpipe,
        level_traditional_set: dancerForm.value.level_traditional_set,
        level_figure: dancerForm.value.level_figure,
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

// Format date for display
const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
};

// Get medal icon/badge for placement
const getMedalBadge = (rank: number) => {
  if (rank === 1) return { icon: '🥇', class: 'bg-amber-100 text-amber-800', label: '1st' };
  if (rank === 2) return { icon: '🥈', class: 'bg-slate-200 text-slate-700', label: '2nd' };
  if (rank === 3) return { icon: '🥉', class: 'bg-orange-100 text-orange-700', label: '3rd' };
  return { icon: '', class: 'bg-slate-100 text-slate-600', label: `${rank}th` };
};

// Count total placements
const totalPlacements = computed(() => {
  return allResults.value.reduce((sum, dancer) => sum + dancer.placements.length, 0);
});
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <!-- Page Header -->
    <div>
      <h1 class="text-3xl font-bold text-slate-800">My Account</h1>
      <p class="text-slate-600 mt-1">View your results, manage your profile and dancers</p>
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

    <!-- Results Section -->
    <section class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-4">
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
          </svg>
          My Results
          <span v-if="totalPlacements > 0" class="ml-2 px-2 py-0.5 bg-white/20 rounded-full text-xs">
            {{ totalPlacements }} placement{{ totalPlacements !== 1 ? 's' : '' }}
          </span>
        </h2>
      </div>
      
      <div class="p-6">
        <!-- Loading -->
        <div v-if="resultsLoading" class="flex items-center justify-center py-12">
          <div class="animate-spin rounded-full h-8 w-8 border-4 border-violet-200 border-t-violet-600"></div>
        </div>
        
        <!-- Empty State -->
        <div v-else-if="totalPlacements === 0" class="text-center py-12">
          <div class="w-16 h-16 bg-violet-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-slate-700 mb-2">No results to show yet</h3>
          <p class="text-slate-500 text-sm">Results from your competitions will appear here after they've been tabulated.</p>
        </div>
        
        <!-- Results List by Dancer -->
        <div v-else class="space-y-6">
          <div
            v-for="dancerResults in allResults.filter(d => d.placements.length > 0)"
            :key="dancerResults.dancer_id"
            class="border border-slate-200 rounded-xl overflow-hidden"
          >
            <!-- Dancer Header -->
            <div class="bg-gradient-to-r from-violet-50 to-purple-50 px-4 py-3 border-b border-slate-200">
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="font-bold text-slate-800 text-lg">{{ dancerResults.dancer_name }}</h4>
                  <p class="text-xs text-slate-600 mt-0.5">{{ dancerResults.placements.length }} result{{ dancerResults.placements.length !== 1 ? 's' : '' }}</p>
                </div>
                <div class="flex gap-2">
                  <div class="text-center px-3 py-1 bg-white rounded-lg shadow-sm">
                    <div class="text-xl font-bold text-amber-600">{{ dancerResults.placements.filter(p => p.rank === 1).length }}</div>
                    <div class="text-xs text-slate-500">1st Place</div>
                  </div>
                  <div class="text-center px-3 py-1 bg-white rounded-lg shadow-sm">
                    <div class="text-xl font-bold text-violet-600">{{ dancerResults.placements.filter(p => p.rank <= 3).length }}</div>
                    <div class="text-xs text-slate-500">Podium</div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Placements List -->
            <div class="divide-y divide-slate-100">
              <div
                v-for="placement in dancerResults.placements"
                :key="placement.id"
                class="px-4 py-3 hover:bg-slate-50 transition-colors"
              >
                <div class="flex items-start justify-between gap-4">
                  <!-- Main Info -->
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                      <span 
                        :class="[
                          'inline-flex items-center gap-1 px-2 py-1 rounded-lg text-sm font-bold',
                          getMedalBadge(placement.rank).class
                        ]"
                      >
                        <span v-if="getMedalBadge(placement.rank).icon">{{ getMedalBadge(placement.rank).icon }}</span>
                        {{ getMedalBadge(placement.rank).label }}
                      </span>
                      <button
                        @click="toggleResultExpansion(placement.id)"
                        class="text-violet-600 hover:text-violet-700 text-sm font-medium flex items-center gap-1"
                      >
                        {{ expandedResults.has(placement.id) ? 'Less' : 'Details' }}
                        <svg 
                          :class="['w-4 h-4 transition-transform', expandedResults.has(placement.id) && 'rotate-180']"
                          fill="none" 
                          stroke="currentColor" 
                          viewBox="0 0 24 24"
                        >
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                    </div>
                    
                    <p class="font-semibold text-slate-800">{{ placement.competition_name }}</p>
                    <p class="text-sm text-slate-600">{{ placement.feis_name }}</p>
                    <p class="text-xs text-slate-500 mt-1">{{ formatDate(placement.competition_date) }}</p>
                    
                    <!-- Expanded Details -->
                    <div v-if="expandedResults.has(placement.id)" class="mt-3 pt-3 border-t border-slate-200 space-y-2">
                      <div class="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span class="text-slate-500">Irish Points:</span>
                          <span class="ml-2 font-semibold text-violet-700">{{ placement.irish_points }}</span>
                        </div>
                        <div>
                          <span class="text-slate-500">Level:</span>
                          <span class="ml-2 font-semibold text-slate-700 capitalize">{{ placement.level.replace('_', ' ') }}</span>
                        </div>
                        <div v-if="placement.dance_type" class="col-span-2">
                          <span class="text-slate-500">Dance:</span>
                          <span class="ml-2 font-semibold text-slate-700 capitalize">{{ placement.dance_type.replace('_', ' ') }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Points Badge -->
                  <div class="text-right">
                    <div class="text-2xl font-bold text-violet-600">{{ placement.irish_points }}</div>
                    <div class="text-xs text-slate-500">points</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

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
                    U{{ getCompetitionAge(dancer.dob) + 1 }}
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
                  <span v-if="dancer.school_id" class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-violet-100 text-violet-800">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                    School Linked
                  </span>
                  <span v-if="dancer.is_adult" class="inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium bg-purple-100 text-purple-800">
                    Adult
                  </span>
                </div>
                <!-- Per-dance level badges (if any differ from main level) -->
                <div 
                  v-if="dancer.level_reel || dancer.level_light_jig || dancer.level_slip_jig || dancer.level_single_jig || dancer.level_treble_jig || dancer.level_hornpipe || dancer.level_traditional_set || dancer.level_figure"
                  class="mt-2 flex flex-wrap gap-1"
                >
                  <span class="text-xs text-slate-400 mr-1">Custom levels:</span>
                  <span v-if="dancer.level_reel" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    🎵 {{ levelOptions.find(l => l.value === dancer.level_reel)?.label }}
                  </span>
                  <span v-if="dancer.level_light_jig" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    💫 {{ levelOptions.find(l => l.value === dancer.level_light_jig)?.label }}
                  </span>
                  <span v-if="dancer.level_slip_jig" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    ✨ {{ levelOptions.find(l => l.value === dancer.level_slip_jig)?.label }}
                  </span>
                  <span v-if="dancer.level_single_jig" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    🪘 {{ levelOptions.find(l => l.value === dancer.level_single_jig)?.label }}
                  </span>
                  <span v-if="dancer.level_treble_jig" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    🥁 {{ levelOptions.find(l => l.value === dancer.level_treble_jig)?.label }}
                  </span>
                  <span v-if="dancer.level_hornpipe" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    ⚡ {{ levelOptions.find(l => l.value === dancer.level_hornpipe)?.label }}
                  </span>
                  <span v-if="dancer.level_traditional_set" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    🌟 {{ levelOptions.find(l => l.value === dancer.level_traditional_set)?.label }}
                  </span>
                  <span v-if="dancer.level_figure" class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    👥 {{ levelOptions.find(l => l.value === dancer.level_figure)?.label }}
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
            
            <!-- Adult Dancer Checkbox -->
            <div class="flex items-center gap-3">
              <button
                type="button"
                @click="dancerForm.is_adult = !dancerForm.is_adult"
                :class="[
                  'w-5 h-5 rounded border-2 flex items-center justify-center transition-all',
                  dancerForm.is_adult
                    ? 'bg-emerald-500 border-emerald-500'
                    : 'border-slate-300 hover:border-emerald-400'
                ]"
              >
                <svg v-if="dancerForm.is_adult" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </button>
              <label class="text-sm text-slate-700 cursor-pointer" @click="dancerForm.is_adult = !dancerForm.is_adult">
                Adult dancer (18+)
              </label>
            </div>

            <!-- Per-Dance Levels (Expandable) -->
            <div class="border border-slate-200 rounded-xl overflow-hidden">
              <button
                type="button"
                @click="showPerDanceLevels = !showPerDanceLevels"
                class="w-full px-4 py-3 flex items-center justify-between bg-slate-50 hover:bg-slate-100 transition-colors"
              >
                <div class="flex items-center gap-2">
                  <svg 
                    :class="['w-4 h-4 transition-transform text-slate-500', showPerDanceLevels && 'rotate-90']" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                  <span class="font-medium text-slate-700 text-sm">Custom levels per dance</span>
                </div>
                <span class="text-xs text-slate-500">Optional</span>
              </button>
              
              <div v-if="showPerDanceLevels" class="p-4 space-y-3 border-t border-slate-200">
                <p class="text-xs text-slate-600 mb-3">
                  Override levels for specific dances. Leave blank to use the main level.
                </p>
                
                <!-- Reel -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">🎵 Reel</span>
                  <select 
                    v-model="dancerForm.level_reel" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Light Jig -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">💫 Light Jig</span>
                  <select 
                    v-model="dancerForm.level_light_jig" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Slip Jig -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">✨ Slip Jig</span>
                  <select 
                    v-model="dancerForm.level_slip_jig" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Single Jig -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">🪘 Single Jig</span>
                  <select 
                    v-model="dancerForm.level_single_jig" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Treble Jig -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">🥁 Treble Jig</span>
                  <select 
                    v-model="dancerForm.level_treble_jig" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Hornpipe -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">⚡ Hornpipe</span>
                  <select 
                    v-model="dancerForm.level_hornpipe" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Traditional Set -->
                <div class="flex items-center gap-3">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">🌟 Trad Set</span>
                  <select 
                    v-model="dancerForm.level_traditional_set" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
                
                <!-- Figure Dances -->
                <div class="flex items-center gap-3 pt-2 border-t border-slate-100">
                  <span class="w-24 text-sm text-slate-700 flex items-center gap-1">👥 Figure</span>
                  <select 
                    v-model="dancerForm.level_figure" 
                    class="flex-1 px-2 py-1.5 text-sm rounded-lg border border-slate-300 focus:border-emerald-500 outline-none"
                  >
                    <option :value="null">Main level</option>
                    <option v-for="opt in levelOptions.filter(o => !['preliminary_championship', 'open_championship'].includes(o.value))" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>
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

            <!-- Dance School / Teacher -->
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-1">
                Dance School / Teacher
                <span class="text-slate-400 font-normal">(Optional)</span>
              </label>
              <div class="relative">
                <!-- Selected Teacher Badge -->
                <div v-if="selectedTeacher" class="flex items-center gap-2 mb-2">
                  <span class="inline-flex items-center gap-2 px-3 py-2 bg-violet-100 text-violet-800 rounded-lg">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                    <span class="font-medium">{{ selectedTeacher.name }}</span>
                    <button 
                      type="button"
                      @click="clearTeacher"
                      class="ml-1 p-0.5 hover:bg-violet-200 rounded"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                </div>
                
                <!-- Search Input -->
                <div v-else class="relative">
                  <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input 
                    type="text" 
                    v-model="teacherSearch"
                    @input="onTeacherSearchInput"
                    @focus="showTeacherDropdown = true"
                    placeholder="Search for teacher or school..."
                    class="w-full pl-10 pr-4 py-2 rounded-xl border-2 border-slate-200 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none"
                  />
                  
                  <!-- Dropdown -->
                  <div 
                    v-if="showTeacherDropdown"
                    class="absolute z-10 mt-1 w-full bg-white border border-slate-200 rounded-xl shadow-lg max-h-48 overflow-y-auto"
                  >
                    <!-- Loading -->
                    <div v-if="teachersLoading" class="flex items-center justify-center py-4">
                      <div class="animate-spin rounded-full h-5 w-5 border-2 border-violet-200 border-t-violet-600"></div>
                    </div>
                    
                    <!-- No Results -->
                    <div v-else-if="teachers.length === 0" class="px-4 py-3 text-sm text-slate-500 text-center">
                      <p>No teachers found</p>
                      <p class="text-xs mt-1">Ask your teacher to register</p>
                    </div>
                    
                    <!-- Results -->
                    <button
                      v-else
                      v-for="teacher in teachers"
                      :key="teacher.id"
                      type="button"
                      @click="selectTeacher(teacher)"
                      class="w-full px-4 py-2 text-left hover:bg-violet-50 transition-colors border-b border-slate-100 last:border-0 flex items-center gap-2"
                    >
                      <div class="w-7 h-7 bg-violet-100 rounded-full flex items-center justify-center flex-shrink-0">
                        <svg class="w-3.5 h-3.5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                      </div>
                      <div>
                        <div class="font-medium text-slate-800 text-sm">{{ teacher.name }}</div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
              <p class="text-xs text-slate-500 mt-1">
                Link to a dance school for teacher visibility
              </p>
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

    <!-- Registration History Section (Collapsible) -->
    <section class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <button
        @click="showRegistrationHistory = !showRegistrationHistory"
        class="w-full bg-gradient-to-r from-slate-600 to-slate-700 px-6 py-4 flex items-center justify-between hover:from-slate-700 hover:to-slate-800 transition-colors"
      >
        <h2 class="text-lg font-bold text-white flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          Registration History
          <span v-if="registrations.length > 0" class="ml-2 px-2 py-0.5 bg-white/20 rounded-full text-xs">
            {{ registrations.length }}
          </span>
        </h2>
        <svg 
          :class="['w-5 h-5 text-white transition-transform', showRegistrationHistory && 'rotate-180']"
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      <div v-if="showRegistrationHistory" class="p-6">
        <!-- Loading -->
        <div v-if="registrationsLoading" class="flex items-center justify-center py-8">
          <div class="animate-spin rounded-full h-8 w-8 border-4 border-orange-200 border-t-orange-600"></div>
        </div>
        
        <!-- Empty State -->
        <div v-else-if="registrations.length === 0" class="text-center py-12">
          <div class="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

