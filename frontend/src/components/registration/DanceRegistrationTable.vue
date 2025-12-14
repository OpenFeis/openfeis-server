<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import type { 
  Competition, 
  Dancer, 
  CompetitionLevel, 
  DanceType,
  CompetitionCategory 
} from '../../models/types';
import { 
  DANCE_TYPE_INFO, 
  SOLO_DANCE_TYPES, 
  FIGURE_DANCE_TYPES 
} from '../../models/types';

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
const loading = ref(false);

// Per-dance level selections (initialized from dancer's levels or current_level)
const soloDanceLevels = ref<Record<string, CompetitionLevel | 'skip'>>({});
// Note: Figure dances are not leveled - they're by age only
const championshipSelections = ref<{ prelim: boolean; open: boolean }>({ prelim: false, open: false });

// Selected competitions
const selectedCompetitionIds = ref<Set<string>>(new Set());

// Level hierarchy for dropdowns
const levelOptions: { value: CompetitionLevel | 'skip'; label: string }[] = [
  { value: 'skip', label: 'Not competing' },
  { value: 'first_feis', label: 'First Feis' },
  { value: 'beginner_1', label: 'Beginner 1' },
  { value: 'beginner_2', label: 'Beginner 2' },
  { value: 'novice', label: 'Novice' },
  { value: 'prizewinner', label: 'Prizewinner' },
  { value: 'preliminary_championship', label: 'Prelim Champ' },
  { value: 'open_championship', label: 'Open Champ' },
];

// Only show grade levels for solo/figure (not championship)
const gradeLevelOptions = levelOptions.filter(
  o => o.value !== 'preliminary_championship' && o.value !== 'open_championship'
);

// Initialize per-dance levels from dancer data
const initializeLevels = () => {
  const defaultLevel = props.dancer.current_level || 'novice';
  
  // Solo dances
  SOLO_DANCE_TYPES.forEach(danceType => {
    const levelKey = `level_${danceType.toLowerCase()}` as keyof Dancer;
    const dancerLevel = props.dancer[levelKey] as CompetitionLevel | undefined;
    soloDanceLevels.value[danceType] = dancerLevel || defaultLevel;
  });
  // Note: Figure dances are not leveled - matched by age only
};

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

// Team Age Selection (defaults to dancer's age, can be increased)
const teamAge = ref<number | null>(null);

// Initialize teamAge when dancerAge becomes available
watch(dancerAge, (newAge) => {
  if (newAge !== null && teamAge.value === null) {
    teamAge.value = newAge;
  }
}, { immediate: true });

// Clear figure dance selections when team age changes
watch(teamAge, (newVal, oldVal) => {
  if (newVal !== oldVal && oldVal !== null) {
    const figureCompIds = new Set(
      allCompetitions.value
        .filter(c => c.category === 'FIGURE' || FIGURE_DANCE_TYPES.includes(c.dance_type as DanceType))
        .map(c => c.id)
    );
    
    const newSelection = new Set(selectedCompetitionIds.value);
    let changed = false;
    for (const id of newSelection) {
      if (figureCompIds.has(id)) {
        newSelection.delete(id);
        changed = true;
      }
    }
    if (changed) {
      selectedCompetitionIds.value = newSelection;
    }
  }
});

const isAdultDancer = computed(() => {
  return props.dancer.is_adult || (dancerAge.value !== null && dancerAge.value >= 18);
});

// Helper to check if a competition matches age and gender
const matchesAgeAndGender = (comp: Competition): boolean => {
  if (dancerAge.value === null || !props.dancer.gender) return false;
  const ageMatch = dancerAge.value >= comp.min_age && dancerAge.value <= comp.max_age;
  // For mixed/open competitions, any gender matches
  const genderMatch = !comp.gender || comp.gender === props.dancer.gender || comp.is_mixed === true;
  return ageMatch && genderMatch;
};

// Helper to check if a competition matches team age and gender
const matchesTeamAgeAndGender = (comp: Competition): boolean => {
  if (teamAge.value === null || !props.dancer.gender) return false;
  const ageMatch = teamAge.value >= comp.min_age && teamAge.value <= comp.max_age;
  // For mixed/open competitions, any gender matches
  const genderMatch = !comp.gender || comp.gender === props.dancer.gender || comp.is_mixed === true;
  return ageMatch && genderMatch;
};

// Find matching competition for a dance type and level
const findMatchingCompetition = (
  danceType: DanceType, 
  level: CompetitionLevel,
  category: CompetitionCategory = 'SOLO'
): Competition | null => {
  return allCompetitions.value.find(comp => {
    // Match category
    const categoryMatch = (comp.category || 'SOLO') === category;
    // Match dance type
    const danceMatch = comp.dance_type === danceType;
    // Match level (not checked for figure dances - they're age-only)
    const levelMatch = category === 'FIGURE' ? true : comp.level === level;
    // Match age and gender
    const demographicMatch = matchesAgeAndGender(comp);
    return categoryMatch && danceMatch && levelMatch && demographicMatch;
  }) || null;
};

// Find figure dance competition (no level requirement)
const findFigureCompetition = (danceType: DanceType): Competition | null => {
  return allCompetitions.value.find(comp => {
    const categoryMatch = (comp.category || 'SOLO') === 'FIGURE' || 
      FIGURE_DANCE_TYPES.includes(comp.dance_type as DanceType);
    const danceMatch = comp.dance_type === danceType;
    const demographicMatch = matchesTeamAgeAndGender(comp);
    return categoryMatch && danceMatch && demographicMatch;
  }) || null;
};

// Find championship competition
const findChampionshipCompetition = (level: 'preliminary_championship' | 'open_championship'): Competition | null => {
  return allCompetitions.value.find(comp => {
    const isChampionship = (comp.category || 'SOLO') === 'CHAMPIONSHIP' || 
      comp.level === 'preliminary_championship' || 
      comp.level === 'open_championship';
    const levelMatch = comp.level === level;
    const demographicMatch = matchesAgeAndGender(comp);
    return isChampionship && levelMatch && demographicMatch;
  }) || null;
};

// Grouped solo dances for display
const soloDanceRows = computed(() => {
  return SOLO_DANCE_TYPES.map(danceType => {
    const level = soloDanceLevels.value[danceType];
    const info = DANCE_TYPE_INFO[danceType];
    const matchedComp = level && level !== 'skip' 
      ? findMatchingCompetition(danceType, level, 'SOLO')
      : null;
    
    return {
      danceType,
      label: info.label,
      icon: info.icon,
      level,
      matchedCompetition: matchedComp,
      isSelected: matchedComp ? selectedCompetitionIds.value.has(matchedComp.id) : false
    };
  });
});

// Figure dance rows (only show if competitions exist)
// Figure dances are NOT leveled - they're by age only
const figureDanceRows = computed(() => {
  return FIGURE_DANCE_TYPES.map(danceType => {
    const info = DANCE_TYPE_INFO[danceType];
    const matchedComp = findFigureCompetition(danceType);
    
    return {
      danceType,
      label: info.label,
      icon: info.icon,
      matchedCompetition: matchedComp,
      isSelected: matchedComp ? selectedCompetitionIds.value.has(matchedComp.id) : false
    };
  }).filter(row => {
    // Only show if there are figure dance competitions of this type that match demographics
    return allCompetitions.value.some(c => 
      c.dance_type === row.danceType && 
      (c.category === 'FIGURE' || FIGURE_DANCE_TYPES.includes(c.dance_type as DanceType)) &&
      matchesTeamAgeAndGender(c)
    );
  });
});

// Has any figure dances available that match dancer's demographics?
const hasFigureDances = computed(() => {
  return allCompetitions.value.some(c => 
    (c.category === 'FIGURE' || FIGURE_DANCE_TYPES.includes(c.dance_type as DanceType)) &&
    matchesTeamAgeAndGender(c)
  );
});

// Championship data
const prelimCompetition = computed(() => findChampionshipCompetition('preliminary_championship'));
const openCompetition = computed(() => findChampionshipCompetition('open_championship'));

const hasChampionships = computed(() => {
  return prelimCompetition.value !== null || openCompetition.value !== null;
});

// Toggle competition selection
const toggleSoloCompetition = (danceType: DanceType) => {
  const row = soloDanceRows.value.find(r => r.danceType === danceType);
  if (!row?.matchedCompetition) return;
  
  const newSet = new Set(selectedCompetitionIds.value);
  if (newSet.has(row.matchedCompetition.id)) {
    newSet.delete(row.matchedCompetition.id);
  } else {
    newSet.add(row.matchedCompetition.id);
  }
  selectedCompetitionIds.value = newSet;
};

const toggleFigureCompetition = (danceType: DanceType) => {
  const row = figureDanceRows.value.find(r => r.danceType === danceType);
  if (!row?.matchedCompetition) return;
  
  const newSet = new Set(selectedCompetitionIds.value);
  if (newSet.has(row.matchedCompetition.id)) {
    newSet.delete(row.matchedCompetition.id);
  } else {
    newSet.add(row.matchedCompetition.id);
  }
  selectedCompetitionIds.value = newSet;
};

const toggleChampionship = (type: 'prelim' | 'open') => {
  const comp = type === 'prelim' ? prelimCompetition.value : openCompetition.value;
  if (!comp) return;
  
  const newSet = new Set(selectedCompetitionIds.value);
  if (newSet.has(comp.id)) {
    newSet.delete(comp.id);
    championshipSelections.value[type] = false;
  } else {
    newSet.add(comp.id);
    championshipSelections.value[type] = true;
  }
  selectedCompetitionIds.value = newSet;
};

// Handle level change - automatically select the matched competition if available
const onSoloLevelChange = (danceType: DanceType, newLevel: CompetitionLevel | 'skip') => {
  soloDanceLevels.value[danceType] = newLevel;
  
  // If changing to 'skip', deselect any previously selected competition for this dance
  if (newLevel === 'skip') {
    const allMatching = allCompetitions.value.filter(c => c.dance_type === danceType);
    const newSet = new Set(selectedCompetitionIds.value);
    allMatching.forEach(c => newSet.delete(c.id));
    selectedCompetitionIds.value = newSet;
  }
};

// Note: Figure dances don't have a level change handler - they're matched by age only

// Emit selected competitions
watch(selectedCompetitionIds, () => {
  const selected = allCompetitions.value.filter(c => selectedCompetitionIds.value.has(c.id));
  emit('select', selected);
}, { deep: true });

// Watch for competitions prop changes
watch(() => props.competitions, (newComps) => {
  if (newComps && newComps.length > 0) {
    allCompetitions.value = newComps;
  }
}, { immediate: true });

// Fetch competitions from API
const fetchCompetitions = async () => {
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
  initializeLevels();
  if (!props.competitions?.length) {
    fetchCompetitions();
  }
});

// Format level for display
const formatLevel = (level: CompetitionLevel | 'skip'): string => {
  if (level === 'skip') return 'Not competing';
  const option = levelOptions.find(o => o.value === level);
  return option?.label || level;
};

// Selection summary
const totalSelected = computed(() => selectedCompetitionIds.value.size);
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
        Choose your level for each dance • {{ dancer.name }}
      </p>
    </div>

    <!-- Dancer Summary Badge -->
    <div class="px-6 py-4 bg-slate-50 border-b border-slate-100">
      <div class="flex flex-wrap gap-2">
        <span v-if="dancerAge !== null" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-amber-100 text-amber-800">
          {{ isAdultDancer ? 'Adult' : `U${dancerAge + 1}` }}
        </span>
        <span v-if="dancer.gender" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
          {{ dancer.gender === 'female' ? 'Girl' : dancer.gender === 'male' ? 'Boy' : 'Other' }}
        </span>
        <span v-if="dancer.current_level" class="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-emerald-100 text-emerald-800">
          {{ formatLevel(dancer.current_level) }}
        </span>
      </div>
    </div>

    <div class="p-6">
      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-10 w-10 border-4 border-orange-200 border-t-orange-600"></div>
      </div>

      <div v-else class="space-y-8">
        <!-- ============= SOLO DANCES SECTION ============= -->
        <section>
          <h3 class="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <span class="w-8 h-8 rounded-lg bg-orange-100 flex items-center justify-center text-orange-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </span>
            Solo Dances
          </h3>
          
          <!-- Mobile Layout: Stacked cards -->
          <div class="md:hidden space-y-3">
            <div 
              v-for="row in soloDanceRows" 
              :key="row.danceType"
              :class="[
                'border rounded-xl p-4 transition-all',
                row.isSelected 
                  ? 'border-orange-400 bg-orange-50' 
                  : 'border-slate-200 bg-white'
              ]"
            >
              <!-- Row 1: Dance name + checkbox -->
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <span class="text-xl">{{ row.icon }}</span>
                  <span class="font-semibold text-slate-700">{{ row.label }}</span>
                </div>
                <button
                  v-if="row.matchedCompetition"
                  @click="toggleSoloCompetition(row.danceType)"
                  :class="[
                    'w-7 h-7 rounded-full flex items-center justify-center transition-all',
                    row.isSelected 
                      ? 'bg-orange-500' 
                      : 'border-2 border-slate-300 hover:border-orange-400'
                  ]"
                >
                  <svg v-if="row.isSelected" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </button>
              </div>
              
              <!-- Row 2: Level selector -->
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs text-slate-500 w-12">Level:</span>
                <select
                  :value="row.level"
                  @change="onSoloLevelChange(row.danceType, ($event.target as HTMLSelectElement).value as CompetitionLevel | 'skip')"
                  class="flex-1 px-3 py-2 rounded-lg border border-slate-300 text-sm focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none bg-white"
                >
                  <option v-for="opt in gradeLevelOptions" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </option>
                </select>
              </div>
              
              <!-- Row 3: Competition match status -->
              <div class="text-sm">
                <span v-if="row.matchedCompetition" class="text-slate-600">
                  {{ row.matchedCompetition.name }}
                </span>
                <span v-else class="text-slate-400 italic">
                  {{ row.level === 'skip' ? 'Not competing' : 'No matching competition' }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- Desktop Layout: Table -->
          <div class="hidden md:block border border-slate-200 rounded-xl overflow-hidden">
            <table class="w-full">
              <thead class="bg-slate-50">
                <tr>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600 w-1/4">Dance</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600 w-1/3">Level</th>
                  <th class="px-4 py-3 text-left text-sm font-semibold text-slate-600">Competition</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="row in soloDanceRows" :key="row.danceType" class="hover:bg-slate-50 transition-colors">
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                      <span class="text-xl">{{ row.icon }}</span>
                      <span class="font-medium text-slate-700">{{ row.label }}</span>
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <select
                      :value="row.level"
                      @change="onSoloLevelChange(row.danceType, ($event.target as HTMLSelectElement).value as CompetitionLevel | 'skip')"
                      class="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:border-orange-500 focus:ring-2 focus:ring-orange-200 transition-all outline-none"
                    >
                      <option v-for="opt in gradeLevelOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                  </td>
                  <td class="px-4 py-3">
                    <button
                      v-if="row.matchedCompetition"
                      @click="toggleSoloCompetition(row.danceType)"
                      :class="[
                        'w-full px-3 py-2 rounded-lg text-left text-sm transition-all border-2 flex items-center justify-between',
                        row.isSelected
                          ? 'bg-orange-50 border-orange-500 text-orange-700'
                          : 'bg-white border-slate-200 text-slate-600 hover:border-orange-300'
                      ]"
                    >
                      <span class="truncate">{{ row.matchedCompetition.name }}</span>
                      <span 
                        :class="[
                          'w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ml-2',
                          row.isSelected ? 'bg-orange-500' : 'border-2 border-slate-300'
                        ]"
                      >
                        <svg v-if="row.isSelected" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                        </svg>
                      </span>
                    </button>
                    <span v-else class="text-slate-400 text-sm italic">
                      {{ row.level === 'skip' ? '—' : 'No matching competition' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- ============= FIGURE DANCES SECTION ============= -->
        <section v-if="hasFigureDances && figureDanceRows.length > 0">
          <h3 class="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <span class="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center text-purple-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </span>
            Figure / Ceili Dances
          </h3>
          
          <!-- Team Age Selection -->
          <div class="mb-4 bg-purple-50 p-4 rounded-xl border border-purple-100 flex flex-col sm:flex-row sm:items-center gap-3">
            <div class="flex-1">
              <label class="block text-sm font-medium text-purple-900 mb-1">Team Age Group</label>
              <p class="text-xs text-purple-700">
                Select the age group for your team. You can dance up, but not down.
              </p>
            </div>
            <select
              v-if="teamAge !== null && dancerAge !== null"
              v-model="teamAge"
              class="w-full sm:w-auto px-3 py-2 rounded-lg border border-purple-200 text-sm focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none bg-white text-purple-900 font-medium"
            >
              <option :value="dancerAge">U{{ dancerAge + 1 }} (Actual)</option>
              <option v-for="i in 10" :key="i" :value="dancerAge + i">
                U{{ dancerAge + i + 1 }}
              </option>
            </select>
          </div>

          <!-- No level selector - figure dances are by age only -->
          <p class="text-sm text-slate-500 mb-3">Team dances available for selected age group:</p>

          <div class="border border-slate-200 rounded-xl overflow-hidden">
            <div class="divide-y divide-slate-100">
              <button
                v-for="row in figureDanceRows"
                :key="row.danceType"
                @click="row.matchedCompetition && toggleFigureCompetition(row.danceType)"
                :disabled="!row.matchedCompetition"
                :class="[
                  'w-full px-4 py-3 text-left transition-all flex items-center justify-between gap-3',
                  row.isSelected
                    ? 'bg-purple-50'
                    : 'bg-white hover:bg-slate-50',
                  !row.matchedCompetition && 'opacity-50 cursor-not-allowed'
                ]"
              >
                <div class="flex items-center gap-3 min-w-0">
                  <span class="text-xl flex-shrink-0">{{ row.icon }}</span>
                  <div class="min-w-0">
                    <span class="font-medium text-slate-700">{{ row.label }}</span>
                    <div v-if="row.matchedCompetition" class="text-xs text-slate-500 truncate">
                      {{ row.matchedCompetition.name }}
                    </div>
                  </div>
                </div>
                <span 
                  v-if="row.matchedCompetition"
                  :class="[
                    'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
                    row.isSelected ? 'bg-purple-500' : 'border-2 border-slate-300'
                  ]"
                >
                  <svg v-if="row.isSelected" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </span>
              </button>
            </div>
          </div>
          
          <p class="text-xs text-slate-500 mt-2">
            <span class="font-medium">Note:</span> One dancer registers for the team.
          </p>
        </section>

        <!-- ============= CHAMPIONSHIP SECTION ============= -->
        <section v-if="hasChampionships">
          <h3 class="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <span class="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-amber-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </span>
            Championship
          </h3>
          
          <div class="space-y-3">
            <!-- Prelim Championship -->
            <button
              v-if="prelimCompetition"
              @click="toggleChampionship('prelim')"
              :class="[
                'w-full px-4 py-4 rounded-xl text-left transition-all border-2 flex items-center justify-between',
                championshipSelections.prelim
                  ? 'bg-amber-50 border-amber-500'
                  : 'bg-white border-slate-200 hover:border-amber-300'
              ]"
            >
              <div>
                <div class="font-semibold text-slate-700">Preliminary Championship</div>
                <div class="text-sm text-slate-500">
                  {{ prelimCompetition.name }}
                  <span class="text-xs ml-1">(3 rounds: Soft Shoe, Hard Shoe, Set)</span>
                </div>
              </div>
              <span 
                :class="[
                  'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
                  championshipSelections.prelim ? 'bg-amber-500' : 'border-2 border-slate-300'
                ]"
              >
                <svg v-if="championshipSelections.prelim" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </span>
            </button>
            
            <!-- Open Championship -->
            <button
              v-if="openCompetition"
              @click="toggleChampionship('open')"
              :class="[
                'w-full px-4 py-4 rounded-xl text-left transition-all border-2 flex items-center justify-between',
                championshipSelections.open
                  ? 'bg-amber-50 border-amber-500'
                  : 'bg-white border-slate-200 hover:border-amber-300'
              ]"
            >
              <div>
                <div class="font-semibold text-slate-700">Open Championship</div>
                <div class="text-sm text-slate-500">
                  {{ openCompetition.name }}
                  <span class="text-xs ml-1">(3 rounds: Soft Shoe, Hard Shoe, Set)</span>
                </div>
              </div>
              <span 
                :class="[
                  'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0',
                  championshipSelections.open ? 'bg-amber-500' : 'border-2 border-slate-300'
                ]"
              >
                <svg v-if="championshipSelections.open" class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
              </span>
            </button>
          </div>
        </section>

        <!-- ============= SELECTION SUMMARY ============= -->
        <div 
          v-if="totalSelected > 0" 
          class="p-4 bg-gradient-to-r from-orange-50 to-amber-50 rounded-xl border border-orange-200"
        >
          <div class="flex items-center justify-between">
            <div>
              <span class="text-lg font-bold text-orange-700">{{ totalSelected }}</span>
              <span class="text-orange-600 ml-1">competition{{ totalSelected !== 1 ? 's' : '' }} selected</span>
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
  </div>
</template>

