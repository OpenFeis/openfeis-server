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
const showAdjacentLevels = ref(false);

// Level hierarchy for filtering
const levelHierarchy: CompetitionLevel[] = [
  'first_feis', 'beginner_1', 'beginner_2', 'novice', 
  'prizewinner', 'preliminary_championship', 'open_championship'
];

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

// Get dancer's level index
const dancerLevelIndex = computed(() => {
  if (!props.dancer.current_level) return -1;
  return levelHierarchy.indexOf(props.dancer.current_level);
});

// Get adjacent level names for display
const adjacentLevelNames = computed(() => {
  const idx = dancerLevelIndex.value;
  const names: string[] = [];
  if (idx > 0) {
    names.push(formatLevel(levelHierarchy[idx - 1]!));
  }
  if (idx < levelHierarchy.length - 1) {
    names.push(formatLevel(levelHierarchy[idx + 1]!));
  }
  return names;
});

// Helper to check age and gender match
const matchesAgeAndGender = (comp: Competition): boolean => {
  if (!dancerAge.value || !props.dancer.gender) return false;
  const ageMatch = dancerAge.value >= comp.min_age && dancerAge.value <= comp.max_age;
  const genderMatch = !comp.gender || comp.gender === props.dancer.gender;
  return ageMatch && genderMatch;
};

// Filter competitions by eligibility - EXACT level match only
const exactLevelCompetitions = computed(() => {
  if (!dancerAge.value || !props.dancer.gender || !props.dancer.current_level) {
    return [];
  }
  
  return allCompetitions.value.filter(comp => {
    const levelMatch = comp.level === props.dancer.current_level;
    return matchesAgeAndGender(comp) && levelMatch;
  });
});

// Adjacent level competitions (one above and one below)
const adjacentLevelCompetitions = computed(() => {
  if (!dancerAge.value || !props.dancer.gender || !props.dancer.current_level) {
    return [];
  }
  
  const idx = dancerLevelIndex.value;
  const adjacentLevels: CompetitionLevel[] = [];
  
  // One level below (if exists)
  if (idx > 0) {
    adjacentLevels.push(levelHierarchy[idx - 1]!);
  }
  // One level above (if exists)
  if (idx < levelHierarchy.length - 1) {
    adjacentLevels.push(levelHierarchy[idx + 1]!);
  }
  
  return allCompetitions.value.filter(comp => {
    const levelMatch = adjacentLevels.includes(comp.level);
    return matchesAgeAndGender(comp) && levelMatch;
  });
});

// Combined eligible competitions (for selection purposes)
const eligibleCompetitions = computed(() => {
  return [...exactLevelCompetitions.value, ...adjacentLevelCompetitions.value];
});

const ineligibleCompetitions = computed(() => {
  const eligibleIds = new Set(eligibleCompetitions.value.map(c => c.id));
  return allCompetitions.value.filter(c => !eligibleIds.has(c.id));
});

// Helper to group competitions by dance type
const groupByDance = (competitions: Competition[]): Record<string, Competition[]> => {
  const groups: Record<string, Competition[]> = {};
  const danceTypes = ['Reel', 'Light Jig', 'Slip Jig', 'Treble Jig', 'Hornpipe', 'Set Dance'];
  
  competitions.forEach(comp => {
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
    groups[dance]!.push(comp);
  });
  
  return groups;
};

// Group exact level competitions by dance type (primary view)
const groupedCompetitions = computed(() => {
  return groupByDance(exactLevelCompetitions.value);
});

// Group adjacent level competitions by dance type (expandable)
const groupedAdjacentCompetitions = computed(() => {
  return groupByDance(adjacentLevelCompetitions.value);
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

// Format level display - convert snake_case to Title Case
const formatLevel = (level: CompetitionLevel): string => {
  const levelNames: Record<CompetitionLevel, string> = {
    'first_feis': 'First Feis',
    'beginner_1': 'Beginner 1',
    'beginner_2': 'Beginner 2',
    'novice': 'Novice',
    'prizewinner': 'Prizewinner',
    'preliminary_championship': 'Preliminary Championship',
    'open_championship': 'Open Championship',
  };
  return levelNames[level] || level.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
};

// Format age range display
const formatAgeRange = (min: number, max: number): string => {
  if (min === max) {
    return `U${min + 1}`;
  }
  return `Ages ${min}-${max}`;
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
    <div class="bg-gradient-to-r from-orange-600 to-amber-700 px-6 py-5">
      <h2 class="text-xl font-bold text-white flex items-center gap-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        Select Competitions
      </h2>
      <p class="text-orange-100 text-sm mt-1">
        Showing {{ formatLevel(dancer.current_level!) }} events for {{ dancer.name }}
      </p>
    </div>

    <!-- Dancer Summary Badge -->
    <div class="px-6 py-4 bg-slate-50 border-b border-slate-100">
      <div class="flex flex-wrap gap-2">
        <span v-if="dancerAge !== null" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-amber-100 text-amber-800">
          U{{ dancerAge + 1 }}
        </span>
        <span v-if="dancer.gender" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
          {{ dancer.gender === 'female' ? 'Girl' : dancer.gender === 'male' ? 'Boy' : 'Other' }}
        </span>
        <span v-if="dancer.current_level" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-emerald-100 text-emerald-800">
          {{ formatLevel(dancer.current_level) }}
        </span>
        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-orange-100 text-orange-800">
          {{ exactLevelCompetitions.length }} at level
        </span>
      </div>
    </div>

    <div class="p-6">
      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-10 w-10 border-4 border-orange-200 border-t-orange-600"></div>
      </div>

      <!-- No Competitions at Exact Level -->
      <div v-else-if="exactLevelCompetitions.length === 0" class="text-center py-8">
        <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No {{ formatLevel(dancer.current_level!) }} Competitions</h3>
        <p class="text-slate-500 text-sm">
          <template v-if="allCompetitions.length === 0">
            No competitions have been created for this feis yet.
          </template>
          <template v-else-if="adjacentLevelCompetitions.length > 0">
            No competitions at this level match the dancer's age/gender, but there are {{ adjacentLevelCompetitions.length }} at adjacent levels.
          </template>
          <template v-else>
            The dancer's profile doesn't match any available competitions.
          </template>
        </p>
        
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
        </div>
      </div>

      <!-- Competition Groups -->
      <div v-else class="space-y-6">
        <div v-for="(comps, dance) in groupedCompetitions" :key="dance">
          <!-- Group Header -->
          <div class="mb-3">
            <h3 class="text-lg font-bold text-slate-700 flex items-center gap-2">
              <span class="text-xl">{{ getDanceIcon(dance) }}</span>
              {{ dance }}
              <span v-if="comps.length > 1" class="text-sm font-normal text-slate-400">({{ comps.length }})</span>
            </h3>
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
                  ? 'bg-orange-50 border-orange-500 ring-2 ring-orange-200'
                  : 'bg-white border-slate-200 hover:border-orange-300 hover:bg-orange-50/50'
              ]"
            >
              <div class="flex items-center justify-between">
                <div>
                  <div :class="[
                    'font-semibold',
                    isSelected(comp.id) ? 'text-orange-700' : 'text-slate-700'
                  ]">
                    {{ comp.name }}
                  </div>
                  <div class="text-xs text-slate-500 mt-0.5">
                    {{ formatAgeRange(comp.min_age, comp.max_age) }} • {{ formatLevel(comp.level) }}
                  </div>
                </div>
                <div 
                  :class="[
                    'w-6 h-6 rounded-full flex items-center justify-center transition-all',
                    isSelected(comp.id)
                      ? 'bg-orange-500'
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

      <!-- Adjacent Levels Section -->
      <div v-if="adjacentLevelCompetitions.length > 0" class="mt-6 pt-6 border-t border-slate-200">
        <button
          @click="showAdjacentLevels = !showAdjacentLevels"
          class="flex items-center gap-2 text-slate-600 hover:text-slate-800 text-sm font-medium transition-colors"
        >
          <svg 
            :class="['w-4 h-4 transition-transform', showAdjacentLevels ? 'rotate-90' : '']" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          {{ showAdjacentLevels ? 'Hide' : 'Show' }} {{ adjacentLevelCompetitions.length }} competitions at other levels
          <span class="text-slate-400 font-normal">({{ adjacentLevelNames.join(', ') }})</span>
        </button>
        
        <div v-if="showAdjacentLevels" class="mt-4">
          <!-- Info Banner -->
          <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl">
            <p class="text-sm text-blue-700">
              <strong>Per-dance levels:</strong> Some dancers compete at different levels for different dances 
              (e.g., Prizewinner in Reel but Novice in Hornpipe). Select these if applicable.
            </p>
          </div>

          <!-- Adjacent Level Competition Groups -->
          <div class="space-y-6">
            <div v-for="(comps, dance) in groupedAdjacentCompetitions" :key="'adj-' + dance">
              <!-- Group Header -->
              <div class="mb-3">
                <h3 class="text-lg font-bold text-slate-600 flex items-center gap-2">
                  <span class="text-xl">{{ getDanceIcon(dance) }}</span>
                  {{ dance }}
                  <span v-if="comps.length > 1" class="text-sm font-normal text-slate-400">({{ comps.length }})</span>
                </h3>
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
                      ? 'bg-blue-50 border-blue-500 ring-2 ring-blue-200'
                      : 'bg-white border-slate-200 hover:border-blue-300 hover:bg-blue-50/50'
                  ]"
                >
                  <div class="flex items-center justify-between">
                    <div>
                      <div class="flex items-center gap-2">
                        <span :class="[
                          'font-semibold',
                          isSelected(comp.id) ? 'text-blue-700' : 'text-slate-700'
                        ]">
                          {{ comp.name }}
                        </span>
                        <span :class="[
                          'text-xs px-1.5 py-0.5 rounded font-medium',
                          comp.level === levelHierarchy[dancerLevelIndex - 1]
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-emerald-100 text-emerald-700'
                        ]">
                          {{ comp.level === levelHierarchy[dancerLevelIndex - 1] ? '↓ Below' : '↑ Above' }}
                        </span>
                      </div>
                      <div class="text-xs text-slate-500 mt-0.5">
                        {{ formatAgeRange(comp.min_age, comp.max_age) }} • {{ formatLevel(comp.level) }}
                      </div>
                    </div>
                    <div 
                      :class="[
                        'w-6 h-6 rounded-full flex items-center justify-center transition-all',
                        isSelected(comp.id)
                          ? 'bg-blue-500'
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
        </div>
      </div>

      <!-- Show Ineligible Toggle -->
      <div v-if="ineligibleCompetitions.length > 0" class="mt-6 pt-6 border-t border-slate-200">
        <button
          @click="showIneligible = !showIneligible"
          class="flex items-center gap-2 text-slate-400 hover:text-slate-600 text-sm font-medium transition-colors"
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
              {{ formatAgeRange(comp.min_age, comp.max_age) }} • {{ formatLevel(comp.level) }}
            </div>
          </div>
        </div>
      </div>

      <!-- Selection Summary -->
      <div 
        v-if="selectedCompetitionIds.size > 0" 
        class="mt-6 p-4 bg-gradient-to-r from-orange-50 to-amber-50 rounded-xl border border-orange-200"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-lg font-bold text-orange-700">{{ selectedCompetitionIds.size }}</span>
            <span class="text-orange-600 ml-1">competition{{ selectedCompetitionIds.size !== 1 ? 's' : '' }} selected</span>
          </div>
          <button 
            @click="selectedCompetitionIds = new Set()"
            class="text-sm text-orange-600 hover:text-orange-800 font-medium"
          >
            Clear All
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
