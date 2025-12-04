<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import type { Dancer, Gender, CompetitionLevel, User } from '../../models/types';

// Props & Emits
const props = defineProps<{
  modelValue?: Partial<Dancer>;
  feisDate?: string; // The feis date to calculate competition age against
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: Partial<Dancer>): void;
  (e: 'submit', dancer: Partial<Dancer>): void;
}>();

// Form State
const name = ref(props.modelValue?.name || '');
const dob = ref(props.modelValue?.dob || '');
const gender = ref<Gender>(props.modelValue?.gender || 'female');
const currentLevel = ref<CompetitionLevel>(props.modelValue?.current_level || 'beginner');
const clrgNumber = ref(props.modelValue?.clrg_number || '');
const schoolId = ref<string>(props.modelValue?.school_id || '');

// Teacher/School Search State
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
let searchTimeout: number | null = null;
const onTeacherSearchInput = () => {
  if (searchTimeout) clearTimeout(searchTimeout);
  searchTimeout = window.setTimeout(() => {
    fetchTeachers(teacherSearch.value);
  }, 300);
};

// Select a teacher
const selectTeacher = (teacher: User) => {
  selectedTeacher.value = teacher;
  schoolId.value = teacher.id;
  teacherSearch.value = teacher.name;
  showTeacherDropdown.value = false;
};

// Clear teacher selection
const clearTeacher = () => {
  selectedTeacher.value = null;
  schoolId.value = '';
  teacherSearch.value = '';
};

// Load initial teachers on mount
onMounted(() => {
  fetchTeachers();
});

// Competition Age Calculation (January 1st Rule)
// In Irish Dancing, your "competition age" is your age as of January 1st
// of the year the competition takes place
const competitionAge = computed(() => {
  if (!dob.value) return null;
  
  const birthDate = new Date(dob.value);
  // Use feis date if provided, otherwise use current year's Jan 1
  const referenceDate = props.feisDate 
    ? new Date(new Date(props.feisDate).getFullYear(), 0, 1) // Jan 1 of feis year
    : new Date(new Date().getFullYear(), 0, 1); // Jan 1 of current year
  
  let age = referenceDate.getFullYear() - birthDate.getFullYear();
  
  // Adjust if birthday hasn't occurred by Jan 1
  const monthDiff = referenceDate.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && referenceDate.getDate() < birthDate.getDate())) {
    age--;
  }
  
  return age;
});

// Age Group Display (e.g., "U12", "O18")
const ageGroup = computed(() => {
  if (competitionAge.value === null) return null;
  const age = competitionAge.value;
  
  if (age >= 18) return 'O18 (Over 18)';
  if (age >= 16) return 'U18';
  if (age >= 14) return 'U16';
  if (age >= 13) return 'U13';
  if (age >= 12) return 'U12';
  if (age >= 11) return 'U11';
  if (age >= 10) return 'U10';
  if (age >= 9) return 'U9';
  if (age >= 8) return 'U8';
  if (age >= 7) return 'U7';
  if (age >= 6) return 'U6';
  return 'U5';
});

// Form Data Object
const formData = computed(() => ({
  name: name.value,
  dob: dob.value,
  gender: gender.value,
  current_level: currentLevel.value,
  clrg_number: clrgNumber.value || undefined,
  school_id: schoolId.value || undefined,
}));

// Update parent on changes
watch(formData, (newVal) => {
  emit('update:modelValue', newVal);
}, { deep: true });

// Validation
const isValid = computed(() => {
  return name.value.trim().length >= 2 && dob.value && competitionAge.value !== null && competitionAge.value >= 4;
});

const validationMessage = computed(() => {
  if (!name.value.trim()) return 'Please enter the dancer\'s name';
  if (name.value.trim().length < 2) return 'Name must be at least 2 characters';
  if (!dob.value) return 'Please enter date of birth';
  if (competitionAge.value !== null && competitionAge.value < 4) return 'Dancer must be at least 4 years old';
  return null;
});

// Submit
const handleSubmit = () => {
  if (isValid.value) {
    emit('submit', formData.value);
  }
};

// Level Options with Descriptions
const levelOptions: { value: CompetitionLevel; label: string; description: string }[] = [
  { value: 'beginner', label: 'Beginner', description: 'First year of competition (Grades 1-3)' },
  { value: 'novice', label: 'Novice', description: 'Beginner with 1st place, or Advanced Beginner' },
  { value: 'prizewinner', label: 'Prizewinner', description: 'Novice with 1st place in solo' },
  { value: 'championship', label: 'Championship', description: 'Open Championship level' },
];

// Gender Options
const genderOptions: { value: Gender; label: string }[] = [
  { value: 'female', label: 'Girl' },
  { value: 'male', label: 'Boy' },
  { value: 'other', label: 'Other' },
];
</script>

<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-5">
      <h2 class="text-xl font-bold text-white flex items-center gap-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        Dancer Profile
      </h2>
      <p class="text-emerald-100 text-sm mt-1">Enter dancer information for competition registration</p>
    </div>

    <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
      <!-- Name Field -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
          Dancer's Full Name
        </label>
        <input 
          type="text" 
          v-model="name"
          placeholder="e.g., Saoirse O'Brien"
          class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none text-slate-800 placeholder-slate-400"
        />
      </div>

      <!-- DOB Field with Age Display -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
          Date of Birth
        </label>
        <div class="flex gap-4 items-start">
          <div class="flex-1">
            <input 
              type="date" 
              v-model="dob"
              :max="new Date().toISOString().split('T')[0]"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none text-slate-800"
            />
          </div>
          <!-- Competition Age Badge -->
          <div 
            v-if="competitionAge !== null"
            class="flex-shrink-0 bg-gradient-to-br from-amber-400 to-orange-500 text-white rounded-xl px-4 py-2 text-center shadow-lg transform transition-all animate-[fadeIn_0.3s_ease-out]"
          >
            <div class="text-2xl font-black">{{ competitionAge }}</div>
            <div class="text-xs font-medium opacity-90">Competition Age</div>
          </div>
        </div>
        <!-- Age Group Indicator -->
        <div v-if="ageGroup" class="mt-2 flex items-center gap-2">
          <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-teal-100 text-teal-800">
            {{ ageGroup }}
          </span>
          <span class="text-xs text-slate-500">
            Based on Jan 1st rule
          </span>
        </div>
      </div>

      <!-- Gender Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
          Category
        </label>
        <div class="grid grid-cols-3 gap-3">
          <button
            v-for="option in genderOptions"
            :key="option.value"
            type="button"
            @click="gender = option.value"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2',
              gender === option.value
                ? 'bg-emerald-600 text-white border-emerald-600 shadow-lg shadow-emerald-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-300 hover:bg-emerald-50'
            ]"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <!-- Level Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
          Current Level
        </label>
        <div class="space-y-2">
          <button
            v-for="option in levelOptions"
            :key="option.value"
            type="button"
            @click="currentLevel = option.value"
            :class="[
              'w-full px-4 py-3 rounded-xl text-left transition-all border-2',
              currentLevel === option.value
                ? 'bg-emerald-50 border-emerald-500 ring-2 ring-emerald-200'
                : 'bg-white border-slate-200 hover:border-emerald-300'
            ]"
          >
            <div class="flex items-center justify-between">
              <div>
                <span :class="[
                  'font-semibold',
                  currentLevel === option.value ? 'text-emerald-700' : 'text-slate-700'
                ]">
                  {{ option.label }}
                </span>
                <p class="text-xs text-slate-500 mt-0.5">{{ option.description }}</p>
              </div>
              <div 
                v-if="currentLevel === option.value"
                class="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center"
              >
                <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
          </button>
        </div>
      </div>

      <!-- CLRG Number (Optional) -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
          CLRG Registration Number
          <span class="text-slate-400 font-normal">(Optional)</span>
        </label>
        <input 
          type="text" 
          v-model="clrgNumber"
          placeholder="e.g., 12345"
          class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none text-slate-800 placeholder-slate-400"
        />
        <p class="text-xs text-slate-500 mt-1">
          Your CLRG number can be found on your dance registration card
        </p>
      </div>

      <!-- Dance School / Teacher (Optional) -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-2">
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
              placeholder="Search for your teacher or school..."
              class="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 focus:border-violet-500 focus:ring-4 focus:ring-violet-100 transition-all outline-none text-slate-800 placeholder-slate-400"
            />
            
            <!-- Dropdown -->
            <div 
              v-if="showTeacherDropdown"
              class="absolute z-10 mt-1 w-full bg-white border border-slate-200 rounded-xl shadow-lg max-h-60 overflow-y-auto"
            >
              <!-- Loading -->
              <div v-if="teachersLoading" class="flex items-center justify-center py-4">
                <div class="animate-spin rounded-full h-5 w-5 border-2 border-violet-200 border-t-violet-600"></div>
              </div>
              
              <!-- No Results -->
              <div v-else-if="teachers.length === 0" class="px-4 py-3 text-sm text-slate-500 text-center">
                <p>No teachers found</p>
                <p class="text-xs mt-1">Ask your teacher to register on Open Feis</p>
              </div>
              
              <!-- Results -->
              <button
                v-else
                v-for="teacher in teachers"
                :key="teacher.id"
                type="button"
                @click="selectTeacher(teacher)"
                class="w-full px-4 py-3 text-left hover:bg-violet-50 transition-colors border-b border-slate-100 last:border-0 flex items-center gap-3"
              >
                <div class="w-8 h-8 bg-violet-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg class="w-4 h-4 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <div>
                  <div class="font-medium text-slate-800">{{ teacher.name }}</div>
                  <div class="text-xs text-slate-500">{{ teacher.email }}</div>
                </div>
              </button>
            </div>
          </div>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Link this dancer to their dance school for teacher visibility
        </p>
      </div>

      <!-- Validation Message -->
      <div 
        v-if="validationMessage && (name || dob)" 
        class="flex items-center gap-2 text-amber-600 bg-amber-50 px-4 py-3 rounded-xl"
      >
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span class="text-sm font-medium">{{ validationMessage }}</span>
      </div>

      <!-- Submit Button -->
      <button
        type="submit"
        :disabled="!isValid"
        :class="[
          'w-full py-4 rounded-xl font-bold text-lg transition-all',
          isValid
            ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-200 hover:shadow-xl hover:shadow-emerald-300 transform hover:-translate-y-0.5'
            : 'bg-slate-200 text-slate-400 cursor-not-allowed'
        ]"
      >
        Save Dancer Profile
      </button>
    </form>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
