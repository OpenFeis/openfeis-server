<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import type { Competition, Dancer, CompetitionLevel } from '../../models/types';

// Props
const props = defineProps<{
  dancer: Partial<Dancer>;
  feisId: string;
  competitions?: Competition[];
}>();

const emit = defineEmits<{
  (e: 'select', competitions: Competition[]): void;
}>();

// State
const allCompetitions = ref<Competition[]>(props.competitions || []);
const selectedCompetitionIds = ref<Set<string>>(new Set());
const loading = ref(false);
const showIneligible = ref(false);

// Watch for changes to competitions prop
watch(() => props.competitions, (newComps) => {
  if (newComps && newComps.length > 0) {
    allCompetitions.value = newComps;
  }
}, { immediate: true });

// Compute dancer's competition age from DOB
const computeCompetitionAge = (dob: string): number => {
  const birthDate = new Date(dob);
  const jan1 = new Date(new Date().getFullYear(), 0, 1);
  let age = jan1.getFullYear() - birthDate.getFullYear();
  const monthDiff = jan1.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && jan1.getDate() < birthDate.getDate())) {
    age--;
  }
  return age;
};

const dancerAge = computed(() => {
  if (!props.dancer.dob) return null;
  return computeCompetitionAge(props.dancer.dob);
});

// Filter competitions by eligibility
const eligibleCompetitions = computed(() => {
  if (!dancerAge.value || !props.dancer.gender || !props.dancer.current_level) {
    return [];
  }
  
  return allCompetitions.value.filter(comp => {
    // Age check
    const ageMatch = dancerAge.value! >= comp.min_age && dancerAge.value! <= comp.max_age;
    
    // Gender check (null means open to all)
    const genderMatch = !comp.gender || comp.gender === props.dancer.gender;
    
    // Level check - dancers can only enter at or below their level
    const levelHierarchy: CompetitionLevel[] = ['beginner', 'novice', 'prizewinner', 'championship'];
    const dancerLevelIndex = levelHierarchy.indexOf(props.dancer.current_level!);
    const compLevelIndex = levelHierarchy.indexOf(comp.level);
    const levelMatch = compLevelIndex <= dancerLevelIndex;
    
    return ageMatch && genderMatch && levelMatch;
  });
});

const ineligibleCompetitions = computed(() => {
  const eligibleIds = new Set(eligibleCompetitions.value.map(c => c.id));
  return allCompetitions.value.filter(c => !eligibleIds.has(c.id));
});

// Group competitions by dance type for better UX
const groupedCompetitions = computed(() => {
  const groups: Record<string, Competition[]> = {};
  
  eligibleCompetitions.value.forEach(comp => {
    // Extract dance type from name (e.g., "Boys U10 Reel (Novice)" -> "Reel")
    const danceTypes = ['Reel', 'Light Jig', 'Slip Jig', 'Treble Jig', 'Hornpipe', 'Set Dance'];
    let dance = 'Other';
    for (const type of danceTypes) {
      if (comp.name.includes(type)) {
        dance = type;
        break;
      }
    }
    
    if (!groups[dance]) {
      groups[dance] = [];
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    groups[dance]!.push(comp);
  });
  
  return groups;
});

// Toggle selection
const toggleSelection = (compId: string) => {
  const newSet = new Set(selectedCompetitionIds.value);
  if (newSet.has(compId)) {
    newSet.delete(compId);
  } else {
    newSet.add(compId);
  }
  selectedCompetitionIds.value = newSet;
};

const isSelected = (compId: string) => selectedCompetitionIds.value.has(compId);

// Select all in a group
const selectAllInGroup = (competitions: Competition[]) => {
  const newSet = new Set(selectedCompetitionIds.value);
  competitions.forEach(c => newSet.add(c.id));
  selectedCompetitionIds.value = newSet;
};

// Clear all in a group
const clearGroup = (competitions: Competition[]) => {
  const newSet = new Set(selectedCompetitionIds.value);
  competitions.forEach(c => newSet.delete(c.id));
  selectedCompetitionIds.value = newSet;
};

// Emit selected competitions
watch(selectedCompetitionIds, () => {
  const selected = eligibleCompetitions.value.filter(c => selectedCompetitionIds.value.has(c.id));
  emit('select', selected);
}, { deep: true });

// Fetch competitions from API
const fetchCompetitions = async () => {
  if (!props.feisId) return;
  
  loading.value = true;
  try {
    const response = await fetch(`/api/v1/feis/${props.feisId}/competitions`);
    if (response.ok) {
      allCompetitions.value = await response.json();
    }
  } catch (error) {
    console.error('Failed to fetch competitions:', error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  if (!props.competitions?.length) {
    fetchCompetitions();
  }
});

// Format level display
const formatLevel = (level: CompetitionLevel): string => {
  return level.charAt(0).toUpperCase() + level.slice(1);
};

// Get icon for dance type
const getDanceIcon = (dance: string): string => {
  const icons: Record<string, string> = {
    'Reel': '🎵',
    'Light Jig': '💫',
    'Slip Jig': '✨',
    'Treble Jig': '🥁',
    'Hornpipe': '⚡',
    'Set Dance': '🌟',
    'Other': '🎶',
  };
  return icons[dance] || '🎶';
};
</script>

<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-5">
      <h2 class="text-xl font-bold text-white flex items-center gap-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        Select Competitions
      </h2>
      <p class="text-violet-100 text-sm mt-1">
        Showing events matching {{ dancer.name }}'s eligibility
      </p>
    </div>

    <!-- Dancer Summary Badge -->
    <div class="px-6 py-4 bg-slate-50 border-b border-slate-100">
      <div class="flex flex-wrap gap-2">
        <span v-if="dancerAge" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-amber-100 text-amber-800">
          Age {{ dancerAge }}
        </span>
        <span v-if="dancer.gender" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
          {{ dancer.gender === 'female' ? 'Girl' : dancer.gender === 'male' ? 'Boy' : 'Other' }}
        </span>
        <span v-if="dancer.current_level" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-emerald-100 text-emerald-800">
          {{ formatLevel(dancer.current_level) }}
        </span>
        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-violet-100 text-violet-800">
          {{ eligibleCompetitions.length }} eligible
        </span>
      </div>
    </div>

    <div class="p-6">
      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-10 w-10 border-4 border-violet-200 border-t-violet-600"></div>
      </div>

      <!-- No Eligible Competitions -->
      <div v-else-if="eligibleCompetitions.length === 0" class="text-center py-8">
        <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No Eligible Competitions</h3>
        
        <!-- Debug Info -->
        <div class="bg-slate-50 rounded-xl p-4 text-left max-w-sm mx-auto mt-4">
          <p class="text-xs font-semibold text-slate-500 mb-2 uppercase">Debug Info:</p>
          <div class="space-y-1 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">Total competitions:</span>
              <span class="font-medium text-slate-700">{{ allCompetitions.length }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Dancer age:</span>
              <span class="font-medium text-slate-700">{{ dancerAge ?? 'Not set' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Dancer level:</span>
              <span class="font-medium text-slate-700">{{ dancer.current_level ?? 'Not set' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">Dancer category:</span>
              <span class="font-medium text-slate-700">{{ dancer.gender ?? 'Not set' }}</span>
            </div>
          </div>
          
          <div v-if="allCompetitions.length > 0" class="mt-3 pt-3 border-t border-slate-200">
            <p class="text-xs text-slate-500 mb-1">Sample competition age ranges:</p>
            <div class="text-xs text-slate-600">
              <div v-for="comp in allCompetitions.slice(0, 3)" :key="comp.id">
                {{ comp.name.substring(0, 30) }}... (ages {{ comp.min_age }}-{{ comp.max_age }})
              </div>
            </div>
          </div>
        </div>
        
        <p class="text-slate-500 text-sm mt-4">
          <template v-if="allCompetitions.length === 0">
            No competitions have been created for this feis yet.
          </template>
          <template v-else>
            The dancer's profile doesn't match any available competitions.
            Try adjusting age, level, or check if competitions exist for their category.
          </template>
        </p>
      </div>

      <!-- Competition Groups -->
      <div v-else class="space-y-6">
        <div v-for="(comps, dance) in groupedCompetitions" :key="dance">
          <!-- Group Header -->
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-bold text-slate-700 flex items-center gap-2">
              <span class="text-xl">{{ getDanceIcon(dance) }}</span>
              {{ dance }}
              <span class="text-sm font-normal text-slate-400">({{ comps.length }})</span>
            </h3>
            <div class="flex gap-2">
              <button 
                @click="selectAllInGroup(comps)"
                class="text-xs px-2 py-1 rounded-lg bg-violet-100 text-violet-700 hover:bg-violet-200 transition-colors font-medium"
              >
                Select All
              </button>
              <button 
                @click="clearGroup(comps)"
                class="text-xs px-2 py-1 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors font-medium"
              >
                Clear
              </button>
            </div>
          </div>

          <!-- Competition Cards -->
          <div class="grid gap-2">
            <button
              v-for="comp in comps"
              :key="comp.id"
              @click="toggleSelection(comp.id)"
              :class="[
                'w-full p-4 rounded-xl text-left transition-all border-2',
                isSelected(comp.id)
                  ? 'bg-violet-50 border-violet-500 ring-2 ring-violet-200'
                  : 'bg-white border-slate-200 hover:border-violet-300 hover:bg-violet-50/50'
              ]"
            >
              <div class="flex items-center justify-between">
                <div>
                  <div :class="[
                    'font-semibold',
                    isSelected(comp.id) ? 'text-violet-700' : 'text-slate-700'
                  ]">
                    {{ comp.name }}
                  </div>
                  <div class="text-xs text-slate-500 mt-0.5">
                    Ages {{ comp.min_age }}-{{ comp.max_age }} • {{ formatLevel(comp.level) }}
                  </div>
                </div>
                <div 
                  :class="[
                    'w-6 h-6 rounded-full flex items-center justify-center transition-all',
                    isSelected(comp.id)
                      ? 'bg-violet-500'
                      : 'border-2 border-slate-300'
                  ]"
                >
                  <svg 
                    v-if="isSelected(comp.id)" 
                    class="w-4 h-4 text-white" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- Show Ineligible Toggle -->
      <div v-if="ineligibleCompetitions.length > 0" class="mt-6 pt-6 border-t border-slate-200">
        <button
          @click="showIneligible = !showIneligible"
          class="flex items-center gap-2 text-slate-500 hover:text-slate-700 text-sm font-medium transition-colors"
        >
          <svg 
            :class="['w-4 h-4 transition-transform', showIneligible ? 'rotate-90' : '']" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          {{ showIneligible ? 'Hide' : 'Show' }} {{ ineligibleCompetitions.length }} ineligible competitions
        </button>
        
        <div v-if="showIneligible" class="mt-4 space-y-2">
          <div
            v-for="comp in ineligibleCompetitions"
            :key="comp.id"
            class="p-3 rounded-xl bg-slate-100 text-slate-400 border border-slate-200"
          >
            <div class="font-medium text-sm">{{ comp.name }}</div>
            <div class="text-xs mt-0.5">
              Ages {{ comp.min_age }}-{{ comp.max_age }} • {{ formatLevel(comp.level) }}
            </div>
          </div>
        </div>
      </div>

      <!-- Selection Summary -->
      <div 
        v-if="selectedCompetitionIds.size > 0" 
        class="mt-6 p-4 bg-gradient-to-r from-violet-50 to-purple-50 rounded-xl border border-violet-200"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-lg font-bold text-violet-700">{{ selectedCompetitionIds.size }}</span>
            <span class="text-violet-600 ml-1">competition{{ selectedCompetitionIds.size !== 1 ? 's' : '' }} selected</span>
          </div>
          <button 
            @click="selectedCompetitionIds = new Set()"
            class="text-sm text-violet-600 hover:text-violet-800 font-medium"
          >
            Clear All
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
