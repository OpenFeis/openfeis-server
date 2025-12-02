<script setup lang="ts">
import { ref, computed } from 'vue';
import type { CompetitionLevel, Gender, SyllabusGenerationRequest, SyllabusGenerationResponse } from '../../models/types';

// Props
const props = defineProps<{
  feisId: string;
  feisName?: string;
}>();

const emit = defineEmits<{
  (e: 'generated', response: SyllabusGenerationResponse): void;
}>();

// Form State
const minAge = ref(5);
const maxAge = ref(18);

// Level selection (multi-select)
const selectedLevels = ref<Set<CompetitionLevel>>(new Set(['beginner', 'novice', 'prizewinner']));

// Gender selection (multi-select)
const selectedGenders = ref<Set<Gender>>(new Set(['male', 'female']));

// Dance selection (multi-select)
const availableDances = ['Reel', 'Light Jig', 'Slip Jig', 'Treble Jig', 'Hornpipe', 'Set Dance'];
const selectedDances = ref<Set<string>>(new Set(['Reel', 'Light Jig', 'Slip Jig']));

// UI State
const isGenerating = ref(false);
const generationResult = ref<SyllabusGenerationResponse | null>(null);
const error = ref<string | null>(null);
const showPreview = ref(true);

// Age groups for display
const ageGroups = computed(() => {
  const groups: string[] = [];
  let age = minAge.value;
  while (age <= maxAge.value) {
    groups.push(`U${age}`);
    age += 2; // Step by 2 years
  }
  return groups;
});

// Estimated competition count
const estimatedCount = computed(() => {
  return ageGroups.value.length * selectedLevels.value.size * selectedGenders.value.size * selectedDances.value.size;
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
  beginner: { label: 'Beginner', color: 'bg-green-100 text-green-700 border-green-300' },
  novice: { label: 'Novice', color: 'bg-blue-100 text-blue-700 border-blue-300' },
  prizewinner: { label: 'Prizewinner', color: 'bg-purple-100 text-purple-700 border-purple-300' },
  championship: { label: 'Championship', color: 'bg-amber-100 text-amber-700 border-amber-300' },
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
  'Treble Jig': '🥁',
  'Hornpipe': '⚡',
  'Set Dance': '🌟',
};

// Generate syllabus
const generateSyllabus = async () => {
  if (estimatedCount.value === 0) {
    error.value = 'Please select at least one option in each category';
    return;
  }

  isGenerating.value = true;
  error.value = null;
  generationResult.value = null;

  const request: SyllabusGenerationRequest = {
    feis_id: props.feisId,
    levels: Array.from(selectedLevels.value),
    min_age: minAge.value,
    max_age: maxAge.value,
    genders: Array.from(selectedGenders.value),
    dances: Array.from(selectedDances.value),
  };

  try {
    const response = await fetch('/api/v1/admin/syllabus/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error('Failed to generate syllabus');
    }

    const result: SyllabusGenerationResponse = await response.json();
    generationResult.value = result;
    emit('generated', result);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
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
      for (const level of selectedLevels.value) {
        for (const dance of selectedDances.value) {
          if (count >= maxPreview) break;
          matrix.push({
            age,
            gender: genderInfo[gender]?.label || gender,
            level: levelInfo[level]?.label || level,
            dance
          });
          count++;
        }
        if (count >= maxPreview) break;
      }
      if (count >= maxPreview) break;
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
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Age Range
        </label>
        <div class="flex items-center gap-4">
          <div class="flex-1">
            <label class="text-xs text-slate-500 mb-1 block">Minimum Age</label>
            <input 
              type="number" 
              v-model.number="minAge" 
              min="4" 
              max="17"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all outline-none text-center text-lg font-bold"
            />
          </div>
          <div class="text-2xl text-slate-400 pt-6">→</div>
          <div class="flex-1">
            <label class="text-xs text-slate-500 mb-1 block">Maximum Age</label>
            <input 
              type="number" 
              v-model.number="maxAge" 
              :min="minAge" 
              max="21"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all outline-none text-center text-lg font-bold"
            />
          </div>
        </div>
        <div class="mt-2 flex flex-wrap gap-1">
          <span 
            v-for="age in ageGroups" 
            :key="age"
            class="px-2 py-1 text-xs rounded-lg bg-indigo-100 text-indigo-700 font-medium"
          >
            {{ age }}
          </span>
        </div>
      </div>

      <!-- Level Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Competition Levels
        </label>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
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
          Categories
        </label>
        <div class="grid grid-cols-3 gap-3">
          <button
            v-for="(info, gender) in genderInfo"
            :key="gender"
            @click="toggleGender(gender as Gender)"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2 flex items-center justify-center gap-2',
              selectedGenders.has(gender as Gender)
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-200'
                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50'
            ]"
          >
            <span class="text-lg">{{ info.icon }}</span>
            {{ info.label }}
          </button>
        </div>
      </div>

      <!-- Dance Selection -->
      <div>
        <label class="block text-sm font-semibold text-slate-700 mb-3">
          Dances
        </label>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
          <button
            v-for="dance in availableDances"
            :key="dance"
            @click="toggleDance(dance)"
            :class="[
              'px-4 py-3 rounded-xl font-semibold transition-all border-2 flex items-center gap-2',
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
          <div class="text-right text-xs text-indigo-500 max-w-[200px]">
            <div>{{ ageGroups.length }} age groups</div>
            <div>× {{ selectedLevels.size }} levels</div>
            <div>× {{ selectedGenders.size }} categories</div>
            <div>× {{ selectedDances.size }} dances</div>
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
