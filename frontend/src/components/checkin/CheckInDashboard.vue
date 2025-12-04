<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { 
  Competition, 
  Feis, 
  Stage,
  CheckInStats,
  CheckInResult,
  StageMonitorEntry
} from '../../models/types';
import { getCheckInStatusBadge } from '../../models/types';

const auth = useAuthStore();

// State
const loading = ref(true);
const error = ref<string | null>(null);

// Selections - Stage-centric workflow
const feiseanna = ref<Feis[]>([]);
const stages = ref<Stage[]>([]);
const competitions = ref<Competition[]>([]);
const selectedFeis = ref<string>('');
const selectedStage = ref<string>('');
const selectedCompetition = ref<string>('');

// Data
const stats = ref<CheckInStats | null>(null);
const entries = ref<StageMonitorEntry[]>([]);
const searchQuery = ref('');
const filterStatus = ref<'all' | 'checked_in' | 'not_checked_in' | 'scratched'>('all');

// QR Scanner
const showQrScanner = ref(false);
const qrInput = ref('');

// Quick number entry
const quickNumberInput = ref('');

// Results
const lastCheckInResult = ref<CheckInResult | null>(null);
const showResultModal = ref(false);

// Current stage info
const currentStage = computed(() => {
  return stages.value.find(s => s.id === selectedStage.value);
});

// Competitions filtered to selected stage
const stageCompetitions = computed(() => {
  if (!selectedStage.value) return [];
  return competitions.value
    .filter(c => c.stage_id === selectedStage.value)
    .sort((a, b) => {
      // Sort by scheduled time, with null times at the end
      if (!a.scheduled_time && !b.scheduled_time) return 0;
      if (!a.scheduled_time) return 1;
      if (!b.scheduled_time) return -1;
      return new Date(a.scheduled_time).getTime() - new Date(b.scheduled_time).getTime();
    });
});

// Current competition details
const currentCompetition = computed(() => {
  return competitions.value.find(c => c.id === selectedCompetition.value);
});

// Filtered entries
const filteredEntries = computed(() => {
  let filtered = entries.value;
  
  // Filter by search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    filtered = filtered.filter(e => 
      e.dancer_name.toLowerCase().includes(query) ||
      (e.competitor_number?.toString() || '').includes(query) ||
      (e.school_name?.toLowerCase() || '').includes(query)
    );
  }
  
  // Filter by status
  if (filterStatus.value !== 'all') {
    filtered = filtered.filter(e => e.check_in_status === filterStatus.value);
  }
  
  return filtered;
});

// Fetch feiseanna
const fetchFeiseanna = async () => {
  try {
    const response = await fetch('/api/v1/feis');
    if (response.ok) {
      feiseanna.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch feiseanna:', e);
  }
};

// Fetch stages for selected feis
const fetchStages = async () => {
  if (!selectedFeis.value) {
    stages.value = [];
    return;
  }
  
  try {
    const response = await fetch(`/api/v1/feis/${selectedFeis.value}/stages`);
    if (response.ok) {
      stages.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch stages:', e);
  }
};

// Fetch all competitions (we'll filter client-side by stage)
const fetchCompetitions = async () => {
  if (!selectedFeis.value) {
    competitions.value = [];
    return;
  }
  
  try {
    const response = await fetch(`/api/v1/feis/${selectedFeis.value}/competitions`);
    if (response.ok) {
      competitions.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch competitions:', e);
  }
};

// Auto-select the closest competition to current time
const autoSelectCompetition = () => {
  if (stageCompetitions.value.length === 0) {
    selectedCompetition.value = '';
    return;
  }
  
  const now = new Date();
  
  // Find competition with scheduled_time closest to now (prefer upcoming)
  let bestMatch = stageCompetitions.value[0];
  let bestDiff = Infinity;
  
  for (const comp of stageCompetitions.value) {
    if (comp.scheduled_time) {
      const compTime = new Date(comp.scheduled_time);
      const diff = compTime.getTime() - now.getTime();
      
      // Prefer upcoming competitions (positive diff), but accept past ones too
      // Give slight preference to upcoming vs past
      const adjustedDiff = diff >= 0 ? diff : Math.abs(diff) * 1.5;
      
      if (adjustedDiff < bestDiff) {
        bestDiff = adjustedDiff;
        bestMatch = comp;
      }
    }
  }
  
  // If no scheduled times, just pick the first one
  if (bestMatch) {
    selectedCompetition.value = bestMatch.id;
  }
};

// Fetch entries for competition
const fetchEntries = async () => {
  if (!selectedCompetition.value) {
    entries.value = [];
    stats.value = null;
    return;
  }
  
  loading.value = true;
  error.value = null;
  
  try {
    // Fetch stage monitor data (includes entries)
    const monitorRes = await auth.authFetch(
      `/api/v1/competitions/${selectedCompetition.value}/stage-monitor`
    );
    
    if (monitorRes.ok) {
      const data = await monitorRes.json();
      entries.value = data.all_entries;
    }
    
    // Fetch stats
    const statsRes = await auth.authFetch(
      `/api/v1/competitions/${selectedCompetition.value}/checkin-stats`
    );
    
    if (statsRes.ok) {
      stats.value = await statsRes.json();
    }
  } catch (e) {
    error.value = 'Failed to load check-in data';
    console.error('Failed to fetch entries:', e);
  } finally {
    loading.value = false;
  }
};

// Check in an entry
const checkIn = async (entryId: string) => {
  try {
    const response = await auth.authFetch('/api/v1/checkin', {
      method: 'POST',
      body: JSON.stringify({ entry_id: entryId })
    });
    
    if (response.ok) {
      lastCheckInResult.value = await response.json();
      showResultModal.value = true;
      
      // Update local state
      const idx = entries.value.findIndex(e => e.entry_id === entryId);
      if (idx >= 0 && entries.value[idx]) {
        (entries.value[idx] as StageMonitorEntry).check_in_status = 'checked_in';
      }
      
      // Refresh stats
      fetchEntries();
    } else {
      const err = await response.json();
      error.value = err.detail || 'Check-in failed';
    }
  } catch (e) {
    error.value = 'Network error during check-in';
    console.error('Check-in failed:', e);
  }
};

// Undo check-in
const undoCheckIn = async (entryId: string) => {
  try {
    const response = await auth.authFetch(`/api/v1/checkin/${entryId}/undo`, {
      method: 'POST'
    });
    
    if (response.ok) {
      // Update local state
      const entry = entries.value.find(e => e.entry_id === entryId);
      if (entry) {
        entry.check_in_status = 'not_checked_in';
      }
      fetchEntries();
    }
  } catch (e) {
    console.error('Undo check-in failed:', e);
  }
};

// Check in by competitor number
const checkInByNumber = async () => {
  if (!quickNumberInput.value || !selectedCompetition.value) return;
  
  const number = parseInt(quickNumberInput.value, 10);
  if (isNaN(number)) {
    error.value = 'Please enter a valid number';
    return;
  }
  
  try {
    const response = await auth.authFetch(
      `/api/v1/checkin/by-number?competition_id=${selectedCompetition.value}&competitor_number=${number}`,
      { method: 'POST' }
    );
    
    if (response.ok) {
      lastCheckInResult.value = await response.json();
      showResultModal.value = true;
      quickNumberInput.value = '';
      fetchEntries();
    } else {
      const err = await response.json();
      error.value = err.detail || 'Check-in failed';
    }
  } catch (e) {
    error.value = 'Network error';
  }
};

// Handle QR scan
const handleQrScan = async () => {
  if (!qrInput.value || !selectedFeis.value) return;
  
  // QR code format: dancer_id or URL with dancer_id
  let dancerId = qrInput.value;
  
  // Extract dancer ID from URL if needed
  const match = qrInput.value.match(/checkin\/([a-f0-9-]+)/);
  if (match && match[1]) {
    dancerId = match[1];
  }
  
  try {
    const response = await auth.authFetch(
      `/api/v1/checkin/qr/${dancerId}?feis_id=${selectedFeis.value}`
    );
    
    if (response.ok) {
      const data = await response.json();
      
      // Filter to entries at this stage
      const stageEntries = data.entries.filter((e: any) => {
        const comp = competitions.value.find(c => c.id === e.competition_id);
        return comp && comp.stage_id === selectedStage.value;
      });
      
      if (stageEntries.length === 0) {
        error.value = 'No entries found for this dancer at this stage';
      } else if (stageEntries.length === 1) {
        // Auto check-in if only one entry at this stage
        await checkIn(stageEntries[0].entry_id);
      } else {
        // Check in all entries at this stage
        for (const entry of stageEntries) {
          if (entry.check_in_status !== 'checked_in') {
            await checkIn(entry.entry_id);
          }
        }
      }
    }
  } catch (e) {
    error.value = 'QR scan failed';
  }
  
  qrInput.value = '';
  showQrScanner.value = false;
};

// Navigate to previous/next competition
const navigateCompetition = (direction: 'prev' | 'next') => {
  const currentIndex = stageCompetitions.value.findIndex(c => c.id === selectedCompetition.value);
  if (currentIndex === -1) return;
  
  const newIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1;
  const nextComp = stageCompetitions.value[newIndex];
  if (newIndex >= 0 && newIndex < stageCompetitions.value.length && nextComp) {
    selectedCompetition.value = nextComp.id;
  }
};

// Format time for display
const formatTime = (dateStr?: string) => {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// Watchers
watch(selectedFeis, () => {
  selectedStage.value = '';
  selectedCompetition.value = '';
  fetchStages();
  fetchCompetitions();
});

watch(selectedStage, () => {
  // Auto-select competition when stage changes
  autoSelectCompetition();
});

watch(selectedCompetition, () => {
  fetchEntries();
});

onMounted(async () => {
  await fetchFeiseanna();
  loading.value = false;
});

// Expose methods for external use (e.g., keyboard shortcuts)
defineExpose({
  checkInByNumber
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header with Stage Selection -->
    <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div 
        class="px-6 py-6"
        :style="currentStage?.color ? { background: `linear-gradient(135deg, ${currentStage.color}, ${currentStage.color}dd)` } : {}"
        :class="!currentStage?.color ? 'bg-gradient-to-r from-teal-600 to-emerald-600' : ''"
      >
        <div class="flex items-center gap-4">
          <div class="w-14 h-14 bg-white/20 rounded-xl flex items-center justify-center">
            <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
          </div>
          <div>
            <h1 class="text-2xl font-bold text-white">
              {{ currentStage ? `${currentStage.name} Check-In` : 'Check-In Dashboard' }}
            </h1>
            <p class="text-white/80 text-sm">
              {{ currentStage ? 'Sidestage check-in for this stage' : 'Select a stage to begin' }}
            </p>
          </div>
        </div>
      </div>
      
      <!-- Stage Selection -->
      <div class="px-6 py-4 border-b border-slate-200 bg-slate-50">
        <div class="flex flex-wrap items-end gap-4">
          <div class="flex-1 min-w-[180px]">
            <label class="block text-sm font-medium text-slate-600 mb-1">Feis</label>
            <select
              v-model="selectedFeis"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            >
              <option value="">Select Feis</option>
              <option v-for="feis in feiseanna" :key="feis.id" :value="feis.id">
                {{ feis.name }}
              </option>
            </select>
          </div>
          
          <div class="flex-1 min-w-[180px]">
            <label class="block text-sm font-medium text-slate-600 mb-1">Stage</label>
            <select
              v-model="selectedStage"
              :disabled="!selectedFeis || stages.length === 0"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500 disabled:opacity-50"
            >
              <option value="">Select Stage</option>
              <option v-for="stage in stages" :key="stage.id" :value="stage.id">
                {{ stage.name }} ({{ stage.competition_count || 0 }} comps)
              </option>
            </select>
          </div>
          
          <div class="flex-1 min-w-[200px]">
            <label class="block text-sm font-medium text-slate-600 mb-1">Competition</label>
            <select
              v-model="selectedCompetition"
              :disabled="!selectedStage || stageCompetitions.length === 0"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500 disabled:opacity-50"
            >
              <option value="">Select Competition</option>
              <option v-for="comp in stageCompetitions" :key="comp.id" :value="comp.id">
                {{ formatTime(comp.scheduled_time) }} - {{ comp.name }}
              </option>
            </select>
          </div>
        </div>
      </div>
      
      <!-- Quick Actions Bar (shown when competition selected) -->
      <div v-if="selectedCompetition" class="px-6 py-3 bg-white border-b border-slate-100 flex flex-wrap items-center gap-4">
        <!-- Navigation -->
        <div class="flex items-center gap-2">
          <button
            @click="navigateCompetition('prev')"
            :disabled="stageCompetitions.findIndex(c => c.id === selectedCompetition) <= 0"
            class="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Previous competition"
          >
            <svg class="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            @click="navigateCompetition('next')"
            :disabled="stageCompetitions.findIndex(c => c.id === selectedCompetition) >= stageCompetitions.length - 1"
            class="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Next competition"
          >
            <svg class="w-4 h-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        
        <!-- Current competition info -->
        <div v-if="currentCompetition" class="flex-1 min-w-[200px]">
          <span class="font-semibold text-slate-800">{{ currentCompetition.name }}</span>
          <span v-if="currentCompetition.scheduled_time" class="text-slate-500 ml-2">
            @ {{ formatTime(currentCompetition.scheduled_time) }}
          </span>
        </div>
        
        <!-- Quick number entry -->
        <div class="flex items-center gap-2">
          <input
            v-model="quickNumberInput"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            placeholder="#"
            class="w-20 px-3 py-2 border border-slate-300 rounded-lg text-center font-bold text-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            @keyup.enter="checkInByNumber"
          />
          <button
            @click="checkInByNumber"
            :disabled="!quickNumberInput"
            class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            Check In
          </button>
        </div>
        
        <!-- QR Scan -->
        <button
          @click="showQrScanner = true"
          class="px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500 transition-colors flex items-center gap-2"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
          </svg>
          Scan
        </button>
      </div>
    </div>

    <!-- Stats -->
    <div v-if="stats" class="grid md:grid-cols-4 gap-4">
      <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-slate-800">{{ stats.total_entries }}</p>
            <p class="text-sm text-slate-500">Total Entries</p>
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-green-600">{{ stats.checked_in }}</p>
            <p class="text-sm text-slate-500">Checked In</p>
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-amber-600">{{ stats.not_checked_in }}</p>
            <p class="text-sm text-slate-500">Waiting</p>
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-red-600">{{ stats.scratched }}</p>
            <p class="text-sm text-slate-500">Scratched</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Entries List -->
    <div v-if="selectedCompetition" class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden">
      <!-- Search & Filter -->
      <div class="px-6 py-4 border-b border-slate-200 flex flex-wrap items-center gap-4">
        <div class="flex-1 min-w-[200px]">
          <div class="relative">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search by name or number..."
              class="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
            />
          </div>
        </div>
        
        <div class="flex items-center gap-2">
          <button
            v-for="status in ['all', 'not_checked_in', 'checked_in', 'scratched']"
            :key="status"
            @click="filterStatus = status as any"
            :class="[
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filterStatus === status
                ? 'bg-teal-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            ]"
          >
            {{ status === 'all' ? 'All' : status === 'not_checked_in' ? 'Waiting' : status === 'checked_in' ? 'Checked In' : 'Scratched' }}
          </button>
        </div>
      </div>
      
      <!-- Table -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-4 border-teal-200 border-t-teal-600"></div>
      </div>
      
      <div v-else-if="filteredEntries.length === 0" class="text-center py-12">
        <p class="text-slate-500">No entries found</p>
      </div>
      
      <div v-else class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-slate-50 text-left">
            <tr>
              <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">#</th>
              <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Dancer</th>
              <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">School</th>
              <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Status</th>
              <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr 
              v-for="entry in filteredEntries" 
              :key="entry.entry_id"
              :class="[
                'hover:bg-slate-50 transition-colors',
                entry.check_in_status === 'scratched' ? 'opacity-50' : ''
              ]"
            >
              <td class="px-6 py-4">
                <span class="text-xl font-bold text-slate-800">
                  {{ entry.competitor_number || '—' }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span class="font-medium text-slate-800">{{ entry.dancer_name }}</span>
              </td>
              <td class="px-6 py-4 text-slate-600">
                {{ entry.school_name || '—' }}
              </td>
              <td class="px-6 py-4">
                <span 
                  :class="[
                    'px-3 py-1 rounded-full text-xs font-semibold',
                    getCheckInStatusBadge(entry.check_in_status).color
                  ]"
                >
                  {{ getCheckInStatusBadge(entry.check_in_status).label }}
                </span>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <button
                    v-if="entry.check_in_status === 'not_checked_in'"
                    @click="checkIn(entry.entry_id)"
                    class="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-500 transition-colors flex items-center gap-1"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    Check In
                  </button>
                  <button
                    v-else-if="entry.check_in_status === 'checked_in'"
                    @click="undoCheckIn(entry.entry_id)"
                    class="px-3 py-1.5 bg-slate-200 text-slate-700 text-sm rounded-lg hover:bg-slate-300 transition-colors"
                  >
                    Undo
                  </button>
                  <span v-else class="text-slate-400 text-sm">N/A</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty State - No Stage Selected -->
    <div v-else-if="!selectedStage" class="bg-white rounded-xl shadow border border-slate-100 p-12 text-center">
      <div class="w-16 h-16 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">Select Your Stage</h3>
      <p class="text-slate-500 max-w-md mx-auto">
        Choose a feis and then select the stage you're working at. The current competition will be auto-selected based on the schedule.
      </p>
    </div>

    <!-- Empty State - No Competitions at Stage -->
    <div v-else-if="stageCompetitions.length === 0" class="bg-white rounded-xl shadow border border-slate-100 p-12 text-center">
      <div class="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Competitions at This Stage</h3>
      <p class="text-slate-500">
        There are no competitions assigned to {{ currentStage?.name || 'this stage' }} yet.
      </p>
    </div>

    <!-- QR Scanner Modal -->
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
          v-if="showQrScanner" 
          class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          @click.self="showQrScanner = false"
        >
          <div class="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden">
            <div class="bg-gradient-to-r from-teal-600 to-emerald-600 px-6 py-4 flex items-center justify-between">
              <h2 class="text-lg font-bold text-white">Scan QR Code</h2>
              <button 
                @click="showQrScanner = false"
                class="p-2 hover:bg-white/20 rounded-lg transition-colors"
              >
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div class="p-6">
              <p class="text-slate-600 mb-4">
                Scan a dancer's QR code to check them in for competitions at <strong>{{ currentStage?.name || 'this stage' }}</strong>.
              </p>
              
              <input
                v-model="qrInput"
                type="text"
                placeholder="Scan or paste QR code content..."
                class="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                @keyup.enter="handleQrScan"
                autofocus
              />
              
              <button
                @click="handleQrScan"
                :disabled="!qrInput"
                class="w-full mt-4 px-4 py-3 bg-teal-600 text-white rounded-xl font-medium hover:bg-teal-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Check In
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Result Modal -->
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
          v-if="showResultModal && lastCheckInResult" 
          class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          @click.self="showResultModal = false"
        >
          <div class="bg-white rounded-2xl shadow-xl max-w-sm w-full overflow-hidden">
            <div 
              :class="[
                'px-6 py-8 text-center',
                lastCheckInResult.status === 'checked_in' 
                  ? 'bg-gradient-to-br from-green-500 to-emerald-600' 
                  : 'bg-gradient-to-br from-red-500 to-rose-600'
              ]"
            >
              <div class="w-20 h-20 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg v-if="lastCheckInResult.status === 'checked_in'" class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                </svg>
                <svg v-else class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              
              <div class="text-6xl font-black text-white mb-2">
                #{{ lastCheckInResult.competitor_number || '—' }}
              </div>
              <div class="text-2xl font-bold text-white">
                {{ lastCheckInResult.dancer_name }}
              </div>
              <div class="text-white/80 mt-2">
                {{ lastCheckInResult.competition_name }}
              </div>
            </div>
            
            <div class="p-6">
              <p class="text-center text-slate-600 mb-4">
                {{ lastCheckInResult.message }}
              </p>
              <button
                @click="showResultModal = false"
                class="w-full px-4 py-3 bg-slate-800 text-white rounded-xl font-medium hover:bg-slate-700 transition-colors"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Error Toast -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="translate-y-2 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div 
          v-if="error" 
          class="fixed bottom-4 right-4 z-50 bg-red-600 text-white px-6 py-4 rounded-xl shadow-lg flex items-center gap-3"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ error }}
          <button @click="error = null" class="ml-2 p-1 hover:bg-white/20 rounded">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
