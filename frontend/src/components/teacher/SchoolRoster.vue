<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { 
  SchoolRoster, 
  SchoolStudent,
  AdvancementCheck
} from '../../models/types';
import { getLevelBadgeColor } from '../../models/types';

const auth = useAuthStore();

// State
const loading = ref(true);
const error = ref<string | null>(null);
const roster = ref<SchoolRoster | null>(null);
const searchQuery = ref('');
const selectedLevel = ref<string>('');

// Modal state
const showAdvancementModal = ref(false);
const selectedStudent = ref<SchoolStudent | null>(null);
const advancementData = ref<AdvancementCheck | null>(null);
const advancementLoading = ref(false);

// Computed: filtered students
const filteredStudents = computed(() => {
  if (!roster.value) return [];
  
  let students = roster.value.students;
  
  // Filter by search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    students = students.filter(s => 
      s.name.toLowerCase().includes(query) ||
      s.parent_name.toLowerCase().includes(query)
    );
  }
  
  // Filter by level
  if (selectedLevel.value) {
    students = students.filter(s => s.current_level === selectedLevel.value);
  }
  
  return students;
});

// Level options
const levelOptions = ['beginner', 'novice', 'prizewinner', 'championship'];

// Fetch roster
const fetchRoster = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/teacher/roster');
    if (response.ok) {
      roster.value = await response.json();
    } else {
      const err = await response.json();
      error.value = err.detail || 'Failed to load roster';
    }
  } catch (e) {
    error.value = 'Network error. Please try again.';
    console.error('Failed to fetch roster:', e);
  } finally {
    loading.value = false;
  }
};

// View student advancement
const viewAdvancement = async (student: SchoolStudent) => {
  selectedStudent.value = student;
  showAdvancementModal.value = true;
  advancementLoading.value = true;
  advancementData.value = null;
  
  try {
    const response = await auth.authFetch(`/api/v1/dancers/${student.id}/advancement`);
    if (response.ok) {
      advancementData.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch advancement:', e);
  } finally {
    advancementLoading.value = false;
  }
};

// Calculate age from DOB
const calculateAge = (dob: string): number => {
  const birthDate = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDiff = today.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
    age--;
  }
  return age;
};

// Calculate competition age (as of Jan 1 of current year)
const competitionAge = (dob: string): number => {
  const birthDate = new Date(dob);
  const jan1 = new Date(new Date().getFullYear(), 0, 1);
  let age = jan1.getFullYear() - birthDate.getFullYear();
  if (birthDate.getMonth() > 0 || (birthDate.getMonth() === 0 && birthDate.getDate() > 1)) {
    // If birthday is after Jan 1, they're technically younger for competition purposes
    // But actually competition age is age on Jan 1, so we check if they've had birthday by Jan 1
    if (birthDate.getMonth() > 0) {
      age--;
    }
  }
  return age;
};

onMounted(() => {
  fetchRoster();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header & Filters -->
    <div class="bg-white rounded-xl shadow border border-slate-100 p-4">
      <div class="flex flex-wrap items-center gap-4">
        <!-- Search -->
        <div class="flex-1 min-w-[200px]">
          <label class="block text-sm font-medium text-slate-600 mb-1">Search</label>
          <div class="relative">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search by name..."
              class="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
            />
          </div>
        </div>
        
        <!-- Level Filter -->
        <div class="w-48">
          <label class="block text-sm font-medium text-slate-600 mb-1">Level</label>
          <select
            v-model="selectedLevel"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
          >
            <option value="">All Levels</option>
            <option v-for="level in levelOptions" :key="level" :value="level" class="capitalize">
              {{ level.charAt(0).toUpperCase() + level.slice(1) }}
            </option>
          </select>
        </div>
        
        <!-- Stats -->
        <div class="flex items-center gap-4 ml-auto">
          <div class="text-center px-4 py-2 bg-violet-50 rounded-lg">
            <p class="text-xl font-bold text-violet-700">{{ filteredStudents.length }}</p>
            <p class="text-xs text-violet-600">Students</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-violet-200 border-t-violet-600"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-xl p-6">
      <div class="flex items-center gap-3">
        <svg class="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <h3 class="font-semibold text-red-800">Error Loading Roster</h3>
          <p class="text-red-600 text-sm">{{ error }}</p>
        </div>
      </div>
      <button 
        @click="fetchRoster"
        class="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
      >
        Try Again
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!roster || roster.students.length === 0" class="text-center py-12 bg-white rounded-xl shadow border border-slate-100">
      <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Students Yet</h3>
      <p class="text-slate-500 text-sm max-w-md mx-auto">
        No dancers are linked to your school yet. Parents can link their dancers to your school from their account settings.
      </p>
    </div>

    <!-- Roster Grid -->
    <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div 
        v-for="student in filteredStudents" 
        :key="student.id"
        class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden hover:shadow-lg transition-shadow"
      >
        <div class="p-5">
          <!-- Student Header -->
          <div class="flex items-start justify-between mb-4">
            <div>
              <h3 class="font-bold text-slate-800 text-lg">{{ student.name }}</h3>
              <p class="text-sm text-slate-500">Parent: {{ student.parent_name }}</p>
            </div>
            <span :class="['px-2 py-1 rounded text-xs font-medium capitalize', getLevelBadgeColor(student.current_level)]">
              {{ student.current_level }}
            </span>
          </div>
          
          <!-- Student Info -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="bg-slate-50 rounded-lg p-3">
              <p class="text-slate-500 text-xs">Age</p>
              <p class="font-semibold text-slate-700">{{ calculateAge(student.dob) }} yrs</p>
            </div>
            <div class="bg-slate-50 rounded-lg p-3">
              <p class="text-slate-500 text-xs">Comp. Age</p>
              <p class="font-semibold text-slate-700">U{{ competitionAge(student.dob) + 1 }}</p>
            </div>
            <div class="bg-slate-50 rounded-lg p-3">
              <p class="text-slate-500 text-xs">Entries</p>
              <p class="font-semibold text-slate-700">{{ student.entry_count }}</p>
            </div>
            <div class="bg-slate-50 rounded-lg p-3">
              <p class="text-slate-500 text-xs">Gender</p>
              <p class="font-semibold text-slate-700 capitalize">{{ student.gender }}</p>
            </div>
          </div>
          
          <!-- Advancement Warning -->
          <div v-if="student.pending_advancements > 0" class="mt-4">
            <button
              @click="viewAdvancement(student)"
              class="w-full px-4 py-2 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg text-sm font-medium hover:bg-amber-100 transition-colors flex items-center justify-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              {{ student.pending_advancements }} Pending Advancement{{ student.pending_advancements > 1 ? 's' : '' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Advancement Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div 
          v-if="showAdvancementModal" 
          class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          @click.self="showAdvancementModal = false"
        >
          <div class="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-hidden">
            <!-- Modal Header -->
            <div class="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 class="text-lg font-bold text-white">Advancement Status</h2>
                <p class="text-amber-100 text-sm">{{ selectedStudent?.name }}</p>
              </div>
              <button 
                @click="showAdvancementModal = false"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
              >
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <!-- Modal Content -->
            <div class="p-6">
              <div v-if="advancementLoading" class="flex items-center justify-center py-8">
                <div class="animate-spin rounded-full h-8 w-8 border-4 border-amber-200 border-t-amber-600"></div>
              </div>
              
              <div v-else-if="advancementData" class="space-y-4">
                <!-- Current Level -->
                <div class="bg-slate-50 rounded-lg p-4">
                  <p class="text-sm text-slate-500 mb-1">Current Level</p>
                  <span :class="['px-3 py-1 rounded text-sm font-medium capitalize', getLevelBadgeColor(advancementData.current_level)]">
                    {{ advancementData.current_level }}
                  </span>
                </div>
                
                <!-- Warnings -->
                <div v-if="advancementData.warnings.length > 0" class="space-y-2">
                  <h4 class="text-sm font-semibold text-slate-700">Advancement Warnings</h4>
                  <div 
                    v-for="(warning, idx) in advancementData.warnings" 
                    :key="idx"
                    class="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2"
                  >
                    <svg class="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p class="text-sm text-amber-800">{{ warning }}</p>
                  </div>
                </div>
                
                <!-- Pending Advancements -->
                <div v-if="advancementData.pending_advancements.length > 0" class="space-y-2">
                  <h4 class="text-sm font-semibold text-slate-700">Pending Advancements</h4>
                  <div 
                    v-for="notice in advancementData.pending_advancements" 
                    :key="notice.id"
                    class="bg-violet-50 border border-violet-200 rounded-lg p-4"
                  >
                    <div class="flex items-center gap-2 mb-2">
                      <span :class="['px-2 py-0.5 rounded text-xs font-medium capitalize', getLevelBadgeColor(notice.from_level)]">
                        {{ notice.from_level }}
                      </span>
                      <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                      </svg>
                      <span :class="['px-2 py-0.5 rounded text-xs font-medium capitalize', getLevelBadgeColor(notice.to_level)]">
                        {{ notice.to_level }}
                      </span>
                    </div>
                    <p class="text-sm text-violet-700">
                      {{ notice.dance_type 
                        ? `Won out for ${notice.dance_type.replace('_', ' ')}` 
                        : 'Won out for all dances' 
                      }}
                    </p>
                    <p class="text-xs text-violet-500 mt-1">
                      {{ new Date(notice.created_at).toLocaleDateString() }}
                    </p>
                  </div>
                </div>
                
                <!-- Eligible Levels -->
                <div class="bg-green-50 rounded-lg p-4">
                  <h4 class="text-sm font-semibold text-green-800 mb-2">Eligible Levels</h4>
                  <div class="flex flex-wrap gap-2">
                    <span 
                      v-for="level in advancementData.eligible_levels" 
                      :key="level"
                      :class="['px-3 py-1 rounded text-sm font-medium capitalize', getLevelBadgeColor(level)]"
                    >
                      {{ level }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Modal Footer -->
            <div class="px-6 py-4 bg-slate-50 border-t border-slate-200">
              <button
                @click="showAdvancementModal = false"
                class="w-full px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

