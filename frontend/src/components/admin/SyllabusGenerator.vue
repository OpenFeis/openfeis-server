<script setup lang="ts">
import { ref, computed } from 'vue';
import type { CompetitionLevel, Gender, SyllabusGenerationRequest, SyllabusGenerationResponse } from '../../models/types';
import { useAuthStore } from '../../stores/auth';

// Props
const props = defineProps<{
  feisId: string;
  feisName?: string;
}>();

const emit = defineEmits<{
  (e: 'generated', response: SyllabusGenerationResponse): void;
}>();

// Form State
const selectedAges = ref<Set<string>>(new Set());

// Available age options
const uAges = Array.from({ length: 16 }, (_, i) => `U${i + 5}`); // U5..U20
const oAges = Array.from({ length: 16 }, (_, i) => `O${i + 5}`); // O5..O20

// Level selection (multi-select)
const selectedLevels = ref<Set<CompetitionLevel>>(new Set());

// Gender selection - default to open (non-gendered) competitions
// Most local feises don't separate by gender for grade competitions
const useGenderedCompetitions = ref(false);
const selectedGenders = ref<Set<Gender>>(new Set(['other'])); // 'other' = open/all genders

// Solo dance selection (multi-select)
const availableSoloDances = ['Reel', 'Light Jig', 'Slip Jig', 'Single Jig', 'Treble Jig', 'Hornpipe', 'Traditional Set', 'Non-Traditional Set'];
const selectedDances = ref<Set<string>>(new Set());

// Figure dance selection (multi-select) - team dances
const availableFigureDances = ['2-Hand', '3-Hand', '4-Hand', '6-Hand', '8-Hand'];
const selectedFigureDances = ref<Set<string>>(new Set());

// Championship options
const includeMixedFigure = ref(true); // For boys entering mixed teams

// Pricing
const priceDollars = ref(10); // Default $10 per competition
// Note: Scoring method is auto-determined (SOLO for grades/figures, CHAMPIONSHIP for champs)

// UI State
const isGenerating = ref(false);
const generationResult = ref<SyllabusGenerationResponse | null>(null);
const error = ref<string | null>(null);
const showPreview = ref(true);

// Toggle age function
const toggleAge = (age: string) => {
  const newSet = new Set(selectedAges.value);
  if (newSet.has(age)) {
    newSet.delete(age);
  } else {
    newSet.add(age);
  }
  selectedAges.value = newSet;
};

// Clear all ages
const clearAges = () => {
  selectedAges.value = new Set();
};

// Age groups for display (sorted)
const ageGroups = computed(() => {
  const ages = Array.from(selectedAges.value);
  return ages.sort((a, b) => {
    if (a === 'Adult') return 1;
    if (b === 'Adult') return -1;
    
    const typeA = a.charAt(0);
    const typeB = b.charAt(0);
    const valA = parseInt(a.slice(1));
    const valB = parseInt(b.slice(1));
    
    if (typeA === typeB) {
      return valA - valB;
    }
    // U comes before O
    return typeA === 'U' ? -1 : 1;
  });
});

// Toggle figure dance

// Toggle figure dance
const toggleFigureDance = (dance: string) => {
  const newSet = new Set(selectedFigureDances.value);
  if (newSet.has(dance)) {
    newSet.delete(dance);
  } else {
    newSet.add(dance);
  }
  selectedFigureDances.value = newSet;
};

// Estimated competition count (solo + figure + champs)
const estimatedSoloCount = computed(() => {
  // Filter out championships from solo count - they are handled separately
  const soloLevels = Array.from(selectedLevels.value).filter(l => 
    l !== 'preliminary_championship' && l !== 'open_championship'
  );
  return ageGroups.value.length * soloLevels.length * selectedGenders.value.size * selectedDances.value.size;
});

const estimatedFigureCount = computed(() => {
  if (selectedFigureDances.value.size === 0) return 0;
  // Figure dances: age groups × dance types × (girls + mixed if enabled)
  // NOT affected by levels or gender presets - figure dances are open level
  const teamCount = 1 + (includeMixedFigure.value ? 1 : 0); // girls-only + mixed
  return ageGroups.value.length * selectedFigureDances.value.size * teamCount;
});

const estimatedChampCount = computed(() => {
  const champLevels = Array.from(selectedLevels.value).filter(l => 
    l === 'preliminary_championship' || l === 'open_championship'
  );
  if (champLevels.length === 0) return 0;
  // Championships are one event per age/gender/level (not per dance)
  return ageGroups.value.length * selectedGenders.value.size * champLevels.length;
});

const estimatedCount = computed(() => {
  return estimatedSoloCount.value + estimatedFigureCount.value + estimatedChampCount.value;
});

// Toggle functions
const toggleLevel = (level: CompetitionLevel) => {
  const newSet = new Set(selectedLevels.value);
  if (newSet.has(level)) {
    newSet.delete(level);
  } else {
    newSet.add(level);
  }
  selectedLevels.value = newSet;
};

const toggleGender = (gender: Gender) => {
  const newSet = new Set(selectedGenders.value);
  if (newSet.has(gender)) {
    newSet.delete(gender);
  } else {
    newSet.add(gender);
  }
  selectedGenders.value = newSet;
};

const toggleDance = (dance: string) => {
  const newSet = new Set(selectedDances.value);
  if (newSet.has(dance)) {
    newSet.delete(dance);
  } else {
    newSet.add(dance);
  }
  selectedDances.value = newSet;
};

// Level descriptions
const levelInfo: Record<CompetitionLevel, { label: string; color: string }> = {
  first_feis: { label: 'First Feis', color: 'bg-pink-100 text-pink-700 border-pink-300' },
  beginner_1: { label: 'Beginner 1', color: 'bg-green-100 text-green-700 border-green-300' },
  beginner_2: { label: 'Beginner 2', color: 'bg-teal-100 text-teal-700 border-teal-300' },
  novice: { label: 'Novice', color: 'bg-blue-100 text-blue-700 border-blue-300' },
  prizewinner: { label: 'Prizewinner', color: 'bg-orange-100 text-orange-700 border-orange-300' },
  preliminary_championship: { label: 'Prelim Champ', color: 'bg-purple-100 text-purple-700 border-purple-300' },
  open_championship: { label: 'Open Champ', color: 'bg-amber-100 text-amber-700 border-amber-300' },
};

// Gender info
const genderInfo: Record<Gender, { label: string; icon: string }> = {
  male: { label: 'Boys', icon: '👦' },
  female: { label: 'Girls', icon: '👧' },
  other: { label: 'Open', icon: '🌟' },
};

// Dance icons
const danceIcons: Record<string, string> = {
  'Reel': '🎵',
  'Light Jig': '💫',
  'Slip Jig': '✨',
  'Single Jig': '🪘',
  'Treble Jig': '🥁',
  'Hornpipe': '⚡',
  'Traditional Set': '🌟',
  'Non-Traditional Set': '💃',
  // Figure dances
  '2-Hand': '👯',
  '3-Hand': '👯',
  '4-Hand': '👥',
  '6-Hand': '👥',
  '8-Hand': '🎭',
};

// Auth store for authenticated requests
const auth = useAuthStore();

// Generate syllabus
const generateSyllabus = async () => {
  if (estimatedCount.value === 0) {
    error.value = 'Please select at least one option in each category';
    return;
  }

  isGenerating.value = true;
  error.value = null;
  generationResult.value = null;

  const request: SyllabusGenerationRequest & { 
    price_cents: number; 
    figure_dances?: string[];
    include_mixed_figure?: boolean;
    selected_ages?: string[];
  } = {
    feis_id: props.feisId,
    levels: Array.from(selectedLevels.value),
    min_age: 0, 
    max_age: 0, 
    selected_ages: Array.from(selectedAges.value),
    genders: Array.from(selectedGenders.value),
    dances: Array.from(selectedDances.value),
    price_cents: priceDollars.value * 100,
    // Figure dances
    figure_dances: selectedFigureDances.value.size > 0 ? Array.from(selectedFigureDances.value) : undefined,
    include_mixed_figure: includeMixedFigure.value,
  };

  try {
    const response = await auth.authFetch('/api/v1/admin/syllabus/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const data = await response.json();
      // Handle different error formats from FastAPI
      let errorMessage = 'Failed to generate syllabus';
      if (data.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (Array.isArray(data.detail)) {
          // FastAPI validation errors come as array of objects
          errorMessage = data.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join(', ');
        } else if (typeof data.detail === 'object') {
          errorMessage = JSON.stringify(data.detail);
        }
      }
      throw new Error(errorMessage);
    }

    const result: SyllabusGenerationResponse = await response.json();
    generationResult.value = result;
    emit('generated', result);
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    isGenerating.value = false;
  }
};

// Preview matrix data
const previewMatrix = computed(() => {
  const matrix: { age: string; gender: string; level: string; dance: string }[] = [];
  
  // Only show first few for preview
  let count = 0;
  const maxPreview = 12;
  
  for (const age of ageGroups.value) {
    for (const gender of selectedGenders.value) {
      // 1. SOLO DANCES & STANDALONE SETS
      for (const level of Array.from(selectedLevels.value)) {
        for (const dance of selectedDances.value) {
          // Skip championships for most dances, but allow them for set dances
          const isChampLevel = level === 'preliminary_championship' || level === 'open_championship';
          const isSetDance = dance === 'Traditional Set' || dance === 'Non-Traditional Set';
          
          if (isChampLevel && !isSetDance) continue;

          if (count >= maxPreview) break;
          matrix.push({
            age,
            gender: genderInfo[gender]?.label || gender,
            level: levelInfo[level as CompetitionLevel]?.label || level,
            dance
          });
          count++;
        }
        if (count >= maxPreview) break;
      }
      if (count >= maxPreview) break;

      // 2. CHAMPIONSHIPS
      const champLevels = Array.from(selectedLevels.value).filter(l => 
        l === 'preliminary_championship' || l === 'open_championship'
      );
      for (const level of champLevels) {
        if (count >= maxPreview) break;
        matrix.push({
          age,
          gender: genderInfo[gender]?.label || gender,
          level: levelInfo[level as CompetitionLevel]?.label || level,
          dance: level === 'preliminary_championship' ? 'Preliminary Championship' : 'Open Championship'
        });
        count++;
      }
      if (count >= maxPreview) break;
    }
    if (count >= maxPreview) break;

    // 3. FIGURE DANCES (if room)
    if (count < maxPreview && selectedFigureDances.value.size > 0) {
      for (const dance of selectedFigureDances.value) {
        if (count >= maxPreview) break;
        matrix.push({
          age,
          gender: 'Girls',
          level: 'Figure',
          dance
        });
        count++;
        
        if (includeMixedFigure.value && count < maxPreview) {
          matrix.push({
            age,
            gender: 'Mixed',
            level: 'Figure',
            dance
          });
          count++;
        }
      }
    }
    if (count >= maxPreview) break;
  }
  
  return matrix;
});
</script>

<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-indigo-600 to-blue-600 px-6 py-5">
      <h2 class="text-xl font-bold text-white flex items-center gap-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
        </svg>
        Syllabus Generator
      </h2>
      <p class="text-indigo-100 text-sm mt-1">
        Auto-generate competitions for {{ feisName || 'your feis' }}
      </p>
    </div>

    <div class="p-6 space-y-6">
      <!-- Age Range -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <label class="block text-sm font-semibold text-slate-700">
            Age Groups
          </label>
          <button 
            @click="clearAges"
            class="text-xs text-red-600 hover:text-red-800 font-medium"
            v-if="selectedAges.size > 0"
          >
            Clear All
          </button>
        </div>
        
        <div class="space-y-1">
          <!-- U Ages Row -->
          <div class="flex items-start gap-2 py-1">
            <div class="w-8 pt-1.5 flex-shrink-0 flex justify-center font-bold text-slate-400 text-sm">U</div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="age in uAges"
                :key="age"
                @click="toggleAge(age)"
                :class="[
                  'px-2 py-1.5 min-w-[2.5rem] rounded-lg text-sm font-semibold transition-all border',
                  selectedAges.has(age)
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-md'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
                ]"
              >
                {{ age.substring(1) }}
              </button>
            </div>
          </div>

          <!-- Divider -->
          <div class="border-t border-slate-100 w-full"></div>

          <!-- O Ages Row -->
          <div class="flex items-start gap-2 py-2 px-3 -mx-3 rounded-xl bg-slate-50/80 border border-transparent hover:border-slate-200/50 transition-colors">
            <div class="w-8 pt-1.5 flex-shrink-0 flex justify-center font-bold text-slate-400 text-sm">O</div>
            <div class="flex flex-wrap gap-2 flex-1 items-center">
              <button
                v-for="age in oAges"
                :key="age"
                @click="toggleAge(age)"
                :class="[
                  'px-2 py-1.5 min-w-[2.5rem] rounded-lg text-sm font-semibold transition-all border',
                  selectedAges.has(age)
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-md'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
                ]"
              >
                {{ age.substring(1) }}
              </button>

              <!-- Spacer to push Adult button to the right if there's room -->
              <div class="flex-grow min-w-[1rem]"></div>

              <button
                @click="toggleAge('Adult')"
                :class="[
                  'px-4 py-1.5 rounded-lg text-sm font-bold transition-all border',
                  selectedAges.has('Adult')
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-md'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
                ]"
              >
                ADULT
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Level Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Competition Levels
        </label>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          <button
            v-for="(info, level) in levelInfo"
            :key="level"
            @click="toggleLevel(level as CompetitionLevel)"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2',
              selectedLevels.has(level as CompetitionLevel)
                ? info.color + ' shadow-md'
                : 'bg-white text-slate-400 border-slate-200 hover:border-slate-300'
            ]"
          >
            {{ info.label }}
          </button>
        </div>
      </div>

      <!-- Gender Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Gender Categories
        </label>
        
        <!-- Toggle for gendered competitions -->
        <div class="flex items-center gap-3 mb-3">
          <button
            type="button"
            @click="useGenderedCompetitions = !useGenderedCompetitions; selectedGenders = new Set(useGenderedCompetitions ? ['male', 'female'] : ['other'])"
            :class="[
              'w-5 h-5 rounded border-2 flex items-center justify-center transition-all',
              useGenderedCompetitions
                ? 'bg-indigo-500 border-indigo-500'
                : 'border-slate-300 hover:border-indigo-400'
            ]"
          >
            <svg v-if="useGenderedCompetitions" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
            </svg>
          </button>
          <label class="text-sm text-slate-700 cursor-pointer" @click="useGenderedCompetitions = !useGenderedCompetitions; selectedGenders = new Set(useGenderedCompetitions ? ['male', 'female'] : ['other'])">
            Create separate Boys and Girls competitions
          </label>
        </div>
        
        <p class="text-xs text-slate-500 mb-3">
          {{ useGenderedCompetitions 
            ? 'Separate competitions will be created for boys and girls (e.g., "Boys U8 Reel", "Girls U8 Reel")' 
            : 'Competitions are open to all genders (e.g., "U8 Reel") — most common for local feiseanna' }}
        </p>
        
        <!-- Only show gender buttons if gendered competitions enabled -->
        <div v-if="useGenderedCompetitions" class="grid grid-cols-2 gap-3">
          <button
            @click="toggleGender('male')"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2 flex items-center justify-center gap-2',
              selectedGenders.has('male')
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
            ]"
          >
            <span class="text-lg">👦</span>
            Boys
          </button>
          <button
            @click="toggleGender('female')"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2 flex items-center justify-center gap-2',
              selectedGenders.has('female')
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
            ]"
          >
            <span class="text-lg">👧</span>
            Girls
          </button>
        </div>
      </div>

      <!-- Solo Dance Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Solo Dances
        </label>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
          <button
            v-for="dance in availableSoloDances"
            :key="dance"
            @click="toggleDance(dance)"
            :class="[
              'px-3 py-2 rounded-xl font-semibold transition-all border-2 flex items-center gap-2 text-sm',
              selectedDances.has(dance)
                ? 'bg-gradient-to-r from-indigo-500 to-blue-500 text-white border-transparent shadow-lg shadow-indigo-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
            ]"
          >
            <span class="text-lg">{{ danceIcons[dance] }}</span>
            {{ dance }}
          </button>
        </div>
      </div>

      <!-- Figure Dance Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Figure / Ceili Dances
          <span class="text-slate-400 font-normal text-xs ml-2">(Team dances — by age only, not leveled)</span>
        </label>
        <div class="grid grid-cols-3 md:grid-cols-5 gap-2">
          <button
            v-for="dance in availableFigureDances"
            :key="dance"
            @click="toggleFigureDance(dance)"
            :class="[
              'px-3 py-2 rounded-xl font-semibold transition-all border-2 flex items-center gap-2 text-sm',
              selectedFigureDances.has(dance)
                ? 'bg-gradient-to-r from-purple-500 to-violet-500 text-white border-transparent shadow-lg shadow-purple-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-purple-300 hover:bg-purple-50'
            ]"
          >
            <span class="text-lg">{{ danceIcons[dance] }}</span>
            {{ dance }}
          </button>
        </div>
        <!-- Mixed figure option -->
        <div v-if="selectedFigureDances.size > 0" class="mt-3 flex items-center gap-3">
          <button
            type="button"
            @click="includeMixedFigure = !includeMixedFigure"
            :class="[
              'w-5 h-5 rounded border-2 flex items-center justify-center transition-all',
              includeMixedFigure
                ? 'bg-purple-500 border-purple-500'
                : 'border-slate-300 hover:border-purple-400'
            ]"
          >
            <svg v-if="includeMixedFigure" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
            </svg>
          </button>
          <label class="text-sm text-slate-700 cursor-pointer" @click="includeMixedFigure = !includeMixedFigure">
            Include mixed-gender teams
          </label>
        </div>
      </div>

      <!-- Pricing -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Price per Competition
        </label>
        <div class="relative max-w-xs">
          <span class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 font-bold">$</span>
          <input 
            type="number" 
            v-model.number="priceDollars" 
            min="0" 
            max="100"
            step="1"
            class="w-full pl-8 pr-4 py-3 rounded-xl border-2 border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all outline-none text-lg font-bold"
          />
        </div>
        <p class="mt-1 text-xs text-slate-500">
          Scoring method is set automatically (Solo for grades/figures, Championship for champs)
        </p>
      </div>

      <!-- Preview Matrix -->
      <div v-if="showPreview && estimatedCount > 0">
        <div class="flex items-center justify-between mb-3">
          <label class="text-sm font-semibold text-slate-700">
            Preview (showing {{ Math.min(12, estimatedCount) }} of {{ estimatedCount }})
          </label>
          <button 
            @click="showPreview = !showPreview"
            class="text-xs text-indigo-600 hover:text-indigo-800"
          >
            {{ showPreview ? 'Hide' : 'Show' }} Preview
          </button>
        </div>
        <div class="bg-slate-50 rounded-xl p-4 max-h-64 overflow-y-auto">
          <div class="grid gap-2">
            <div
              v-for="(item, index) in previewMatrix"
              :key="index"
              class="flex items-center gap-2 text-sm bg-white rounded-lg px-3 py-2 border border-slate-200"
            >
              <span class="font-mono text-slate-400 w-8">#{{ index + 1 }}</span>
              <span class="font-medium text-slate-700">{{ item.gender }}</span>
              <span class="text-indigo-600">{{ item.age }}</span>
              <span class="text-slate-500">{{ item.dance }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                {{ item.level }}
              </span>
            </div>
            <div 
              v-if="estimatedCount > 12"
              class="text-center text-sm text-slate-500 py-2"
            >
              ... and {{ estimatedCount - 12 }} more competitions
            </div>
          </div>
        </div>
      </div>

      <!-- Estimated Count -->
      <div class="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-xl p-4 border border-indigo-100">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm text-indigo-600 font-medium">Estimated Competitions</div>
            <div class="text-3xl font-black text-indigo-700">{{ estimatedCount }}</div>
          </div>
          <div class="text-right text-xs text-indigo-500 max-w-[220px] space-y-0.5">
            <div v-if="estimatedSoloCount > 0">
              <span class="font-medium">{{ estimatedSoloCount }}</span> solo
              <span class="text-indigo-400">({{ ageGroups.length }} ages × {{ selectedLevels.size }} levels × {{ selectedGenders.size }} genders × {{ selectedDances.size }} dances)</span>
            </div>
            <div v-if="estimatedFigureCount > 0">
              <span class="font-medium">{{ estimatedFigureCount }}</span> figure
              <span class="text-indigo-400">({{ ageGroups.length }} ages × {{ selectedFigureDances.size }} dances{{ includeMixedFigure ? ' × 2 teams' : '' }})</span>
            </div>
            <div v-if="estimatedChampCount > 0">
              <span class="font-medium">{{ estimatedChampCount }}</span> championships
              <span class="text-indigo-400">({{ ageGroups.length }} ages × {{ selectedGenders.size }} genders)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <div 
        v-if="error" 
        class="flex items-center gap-2 text-red-600 bg-red-50 px-4 py-3 rounded-xl"
      >
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-sm font-medium">{{ error }}</span>
      </div>

      <!-- Success Message -->
      <div 
        v-if="generationResult" 
        class="flex items-center gap-3 bg-emerald-50 px-4 py-4 rounded-xl border border-emerald-200"
      >
        <div class="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
          <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <div class="font-semibold text-emerald-700">{{ generationResult.message }}</div>
          <div class="text-sm text-emerald-600">{{ generationResult.generated_count }} competitions created</div>
        </div>
      </div>

      <!-- Generate Button -->
      <button
        @click="generateSyllabus"
        :disabled="isGenerating || estimatedCount === 0"
        :class="[
          'w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2',
          isGenerating || estimatedCount === 0
            ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
            : 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white shadow-lg shadow-indigo-200 hover:shadow-xl hover:shadow-indigo-300 transform hover:-translate-y-0.5'
        ]"
      >
        <template v-if="isGenerating">
          <div class="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
          Generating...
        </template>
        <template v-else>
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Generate {{ estimatedCount }} Competitions
        </template>
      </button>
    </div>
  </div>
</template>
