<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { 
  TeacherDashboard, 
  TeacherStudentEntry,
  AdvancementNotice,
  Feis
} from '../../models/types';
import { getLevelBadgeColor, formatCents } from '../../models/types';
import SchoolRoster from './SchoolRoster.vue';

const auth = useAuthStore();

// State
const loading = ref(true);
const error = ref<string | null>(null);
const dashboard = ref<TeacherDashboard | null>(null);
const activeTab = ref<'overview' | 'roster' | 'entries' | 'flags'>('overview');

// Filters
const selectedFeisId = ref<string>('');
const availableFeiseanna = ref<Feis[]>([]);

// Entries
const entries = ref<TeacherStudentEntry[]>([]);
const entriesLoading = ref(false);

// Emit for navigation
const emit = defineEmits<{
  (e: 'view-dancer', dancerId: string): void;
  (e: 'view-entry', entryId: string): void;
}>();

// Fetch dashboard data
const fetchDashboard = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/teacher/dashboard');
    if (response.ok) {
      dashboard.value = await response.json();
    } else {
      const err = await response.json();
      error.value = err.detail || 'Failed to load dashboard';
    }
  } catch (e) {
    error.value = 'Network error. Please try again.';
    console.error('Failed to fetch teacher dashboard:', e);
  } finally {
    loading.value = false;
  }
};

// Fetch available feiseanna
const fetchFeiseanna = async () => {
  try {
    const response = await fetch('/api/v1/feis');
    if (response.ok) {
      availableFeiseanna.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch feiseanna:', e);
  }
};

// Fetch entries for a specific feis
const fetchEntries = async () => {
  entriesLoading.value = true;
  
  try {
    const url = selectedFeisId.value 
      ? `/api/v1/teacher/entries?feis_id=${selectedFeisId.value}`
      : '/api/v1/teacher/entries';
    
    const response = await auth.authFetch(url);
    if (response.ok) {
      entries.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to fetch entries:', e);
  } finally {
    entriesLoading.value = false;
  }
};

// Export entries
const exportEntries = async (format: 'csv' | 'json') => {
  try {
    const url = selectedFeisId.value
      ? `/api/v1/teacher/export?feis_id=${selectedFeisId.value}&format=${format}`
      : `/api/v1/teacher/export?format=${format}`;
    
    const response = await auth.authFetch(url);
    
    if (format === 'csv') {
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `school_entries_${selectedFeisId.value || 'all'}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
    } else {
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `school_entries_${selectedFeisId.value || 'all'}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
    }
  } catch (e) {
    console.error('Failed to export entries:', e);
  }
};

// Computed: entries grouped by feis
const entriesByFeis = computed(() => {
  const grouped: Record<string, { feis_name: string; entries: TeacherStudentEntry[] }> = {};
  
  for (const entry of entries.value) {
    if (!grouped[entry.feis_id]) {
      grouped[entry.feis_id] = {
        feis_name: entry.feis_name,
        entries: []
      };
    }
    grouped[entry.feis_id].entries.push(entry);
  }
  
  return grouped;
});

// Computed: flagged entries count
const flaggedEntriesCount = computed(() => {
  return entries.value.filter(e => e.is_flagged).length;
});

onMounted(async () => {
  await Promise.all([
    fetchDashboard(),
    fetchFeiseanna()
  ]);
  await fetchEntries();
});

// Watch for feis filter change
const onFeisChange = () => {
  fetchEntries();
};
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
      <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-14 h-14 bg-white/20 rounded-xl flex items-center justify-center">
              <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div>
              <h1 class="text-2xl font-bold text-white">Teacher Dashboard</h1>
              <p class="text-violet-200 text-sm">{{ dashboard?.teacher_name || 'Loading...' }}</p>
            </div>
          </div>
          
          <!-- Quick Stats -->
          <div v-if="dashboard" class="hidden md:flex items-center gap-6">
            <div class="text-center">
              <p class="text-3xl font-bold text-white">{{ dashboard.total_students }}</p>
              <p class="text-violet-200 text-xs uppercase tracking-wide">Students</p>
            </div>
            <div class="text-center">
              <p class="text-3xl font-bold text-white">{{ dashboard.total_entries }}</p>
              <p class="text-violet-200 text-xs uppercase tracking-wide">Entries</p>
            </div>
            <div v-if="dashboard.pending_advancements > 0" class="text-center">
              <p class="text-3xl font-bold text-amber-300">{{ dashboard.pending_advancements }}</p>
              <p class="text-violet-200 text-xs uppercase tracking-wide">Advancements</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Tab Navigation -->
      <div class="border-b border-slate-200">
        <nav class="flex gap-1 px-6" aria-label="Tabs">
          <button
            @click="activeTab = 'overview'"
            :class="[
              'px-4 py-3 text-sm font-medium border-b-2 transition-all',
              activeTab === 'overview'
                ? 'border-violet-500 text-violet-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            ]"
          >
            Overview
          </button>
          <button
            @click="activeTab = 'roster'"
            :class="[
              'px-4 py-3 text-sm font-medium border-b-2 transition-all',
              activeTab === 'roster'
                ? 'border-violet-500 text-violet-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            ]"
          >
            School Roster
          </button>
          <button
            @click="activeTab = 'entries'"
            :class="[
              'px-4 py-3 text-sm font-medium border-b-2 transition-all',
              activeTab === 'entries'
                ? 'border-violet-500 text-violet-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            ]"
          >
            All Entries
          </button>
        </nav>
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
          <h3 class="font-semibold text-red-800">Error Loading Dashboard</h3>
          <p class="text-red-600 text-sm">{{ error }}</p>
        </div>
      </div>
      <button 
        @click="fetchDashboard"
        class="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
      >
        Try Again
      </button>
    </div>

    <!-- Content -->
    <template v-else-if="dashboard">
      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'" class="space-y-6">
        <!-- Stats Cards -->
        <div class="grid md:grid-cols-4 gap-4">
          <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-violet-100 rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <div>
                <p class="text-2xl font-bold text-slate-800">{{ dashboard.total_students }}</p>
                <p class="text-sm text-slate-500">Students</p>
              </div>
            </div>
          </div>
          
          <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <div>
                <p class="text-2xl font-bold text-slate-800">{{ dashboard.total_entries }}</p>
                <p class="text-sm text-slate-500">Total Entries</p>
              </div>
            </div>
          </div>
          
          <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <div>
                <p class="text-2xl font-bold text-slate-800">{{ dashboard.pending_advancements }}</p>
                <p class="text-sm text-slate-500">Pending Advancements</p>
              </div>
            </div>
          </div>
          
          <div class="bg-white rounded-xl p-5 shadow border border-slate-100">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-rose-100 rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                </svg>
              </div>
              <div>
                <p class="text-2xl font-bold text-slate-800">{{ flaggedEntriesCount }}</p>
                <p class="text-sm text-slate-500">Flagged Entries</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Entries by Feis -->
        <div v-if="Object.keys(dashboard.entries_by_feis).length > 0" class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden">
          <div class="px-6 py-4 border-b border-slate-100">
            <h2 class="text-lg font-bold text-slate-800">Entries by Feis</h2>
          </div>
          <div class="divide-y divide-slate-100">
            <div 
              v-for="(count, feisId) in dashboard.entries_by_feis" 
              :key="feisId"
              class="px-6 py-4 flex items-center justify-between hover:bg-slate-50"
            >
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
                  <svg class="w-4 h-4 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <span class="font-medium text-slate-700">
                  {{ availableFeiseanna.find(f => f.id === feisId)?.name || feisId }}
                </span>
              </div>
              <span class="px-3 py-1 bg-violet-100 text-violet-700 rounded-full text-sm font-medium">
                {{ count }} entries
              </span>
            </div>
          </div>
        </div>

        <!-- Recent Entries -->
        <div v-if="dashboard.recent_entries.length > 0" class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden">
          <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 class="text-lg font-bold text-slate-800">Recent Entries</h2>
            <button 
              @click="activeTab = 'entries'"
              class="text-sm text-violet-600 hover:text-violet-700 font-medium"
            >
              View All →
            </button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead class="bg-slate-50 text-left">
                <tr>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Dancer</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Competition</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Level</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Feis</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr 
                  v-for="entry in dashboard.recent_entries.slice(0, 10)" 
                  :key="entry.entry_id"
                  class="hover:bg-slate-50"
                >
                  <td class="px-6 py-4">
                    <span class="font-medium text-slate-800">{{ entry.dancer_name }}</span>
                  </td>
                  <td class="px-6 py-4 text-slate-600">{{ entry.competition_name }}</td>
                  <td class="px-6 py-4">
                    <span :class="['px-2 py-1 rounded text-xs font-medium capitalize', getLevelBadgeColor(entry.level)]">
                      {{ entry.level }}
                    </span>
                  </td>
                  <td class="px-6 py-4 text-slate-600 text-sm">{{ entry.feis_name }}</td>
                  <td class="px-6 py-4">
                    <div class="flex items-center gap-2">
                      <span v-if="entry.paid" class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                        Paid
                      </span>
                      <span v-else class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                        Unpaid
                      </span>
                      <span v-if="entry.is_flagged" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium flex items-center gap-1">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                        </svg>
                        Flagged
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Roster Tab -->
      <div v-else-if="activeTab === 'roster'">
        <SchoolRoster />
      </div>

      <!-- Entries Tab -->
      <div v-else-if="activeTab === 'entries'" class="space-y-4">
        <!-- Filters & Actions -->
        <div class="bg-white rounded-xl shadow border border-slate-100 p-4">
          <div class="flex flex-wrap items-center gap-4">
            <!-- Feis Filter -->
            <div class="flex-1 min-w-[200px]">
              <label class="block text-sm font-medium text-slate-600 mb-1">Filter by Feis</label>
              <select
                v-model="selectedFeisId"
                @change="onFeisChange"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
              >
                <option value="">All Feiseanna</option>
                <option v-for="feis in availableFeiseanna" :key="feis.id" :value="feis.id">
                  {{ feis.name }}
                </option>
              </select>
            </div>
            
            <!-- Export Buttons -->
            <div class="flex items-end gap-2">
              <button
                @click="exportEntries('csv')"
                class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export CSV
              </button>
              <button
                @click="exportEntries('json')"
                class="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Export JSON
              </button>
            </div>
          </div>
        </div>

        <!-- Entries Table -->
        <div class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden">
          <div v-if="entriesLoading" class="flex items-center justify-center py-12">
            <div class="animate-spin rounded-full h-8 w-8 border-4 border-violet-200 border-t-violet-600"></div>
          </div>
          
          <div v-else-if="entries.length === 0" class="text-center py-12">
            <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h3 class="text-lg font-semibold text-slate-700 mb-2">No Entries Found</h3>
            <p class="text-slate-500 text-sm">
              {{ selectedFeisId ? 'No students from your school are registered for this feis.' : 'No students from your school have registered for any feis yet.' }}
            </p>
          </div>
          
          <div v-else class="overflow-x-auto">
            <table class="w-full">
              <thead class="bg-slate-50 text-left">
                <tr>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">#</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Dancer</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Competition</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Level</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Feis</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Date</th>
                  <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr 
                  v-for="entry in entries" 
                  :key="entry.entry_id"
                  class="hover:bg-slate-50"
                >
                  <td class="px-6 py-4">
                    <span class="font-mono text-sm text-slate-600">
                      {{ entry.competitor_number || '—' }}
                    </span>
                  </td>
                  <td class="px-6 py-4">
                    <span class="font-medium text-slate-800">{{ entry.dancer_name }}</span>
                  </td>
                  <td class="px-6 py-4 text-slate-600">{{ entry.competition_name }}</td>
                  <td class="px-6 py-4">
                    <span :class="['px-2 py-1 rounded text-xs font-medium capitalize', getLevelBadgeColor(entry.level)]">
                      {{ entry.level }}
                    </span>
                  </td>
                  <td class="px-6 py-4 text-slate-600 text-sm">{{ entry.feis_name }}</td>
                  <td class="px-6 py-4 text-slate-500 text-sm">{{ entry.feis_date }}</td>
                  <td class="px-6 py-4">
                    <div class="flex items-center gap-2">
                      <span v-if="entry.paid" class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                        Paid
                      </span>
                      <span v-else class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                        Unpaid
                      </span>
                      <span v-if="entry.is_flagged" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium flex items-center gap-1">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                        </svg>
                        Flagged
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

