<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { syncService, type SyncConflict, type PendingSyncData } from '../../services/syncService';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';

// Auth store for API token
const authStore = useAuthStore();
const { token } = storeToRefs(authStore);

// Local state
const pendingData = ref<PendingSyncData | null>(null);
const isCheckingPending = ref(false);
const cloudServerUrl = ref('');
const showConflicts = ref(false);

// Sync service reactive state
const { progress, isSyncing, lastSyncResult } = syncService;

// Computed
const hasPendingData = computed(() => (pendingData.value?.totalCount ?? 0) > 0);
const hasConflicts = computed(() => (lastSyncResult.value?.conflicts?.length ?? 0) > 0);

const progressPercent = computed(() => {
  if (progress.value.total === 0) return 0;
  return Math.round((progress.value.current / progress.value.total) * 100);
});

const statusColor = computed(() => {
  switch (progress.value.phase) {
    case 'complete':
      return lastSyncResult.value?.success ? 'emerald' : 'amber';
    case 'error':
      return 'red';
    case 'uploading':
    case 'verifying':
      return 'blue';
    default:
      return 'slate';
  }
});

// Methods
async function checkPendingData() {
  isCheckingPending.value = true;
  try {
    pendingData.value = await syncService.getPendingData();
  } catch (error) {
    console.error('Failed to check pending data:', error);
  } finally {
    isCheckingPending.value = false;
  }
}

async function startSync() {
  if (!cloudServerUrl.value) {
    alert('Please enter the cloud server URL');
    return;
  }

  // Set auth token for API requests
  syncService.setAuthToken(token.value);

  await syncService.syncToCloud(cloudServerUrl.value);
  
  // Refresh pending data count
  await checkPendingData();
}

async function resolveConflict(conflict: SyncConflict, resolution: 'use_local' | 'use_server') {
  const success = await syncService.resolveConflict(cloudServerUrl.value, conflict, resolution);
  
  if (success) {
    // Remove resolved conflict from the list
    if (lastSyncResult.value) {
      lastSyncResult.value.conflicts = lastSyncResult.value.conflicts.filter(
        c => c.score_id !== conflict.score_id
      );
    }
  } else {
    alert('Failed to resolve conflict. Please try again.');
  }
}

function resetSync() {
  syncService.reset();
  pendingData.value = null;
}

// Initialize
onMounted(() => {
  checkPendingData();
  
  // Default to current origin if we're already on the cloud
  if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    cloudServerUrl.value = window.location.origin;
  }
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-slate-800">Cloud Sync</h2>
        <p class="text-slate-600 mt-1">
          Upload local scores to the cloud server after running offline
        </p>
      </div>
      
      <button
        @click="checkPendingData"
        :disabled="isCheckingPending"
        class="px-4 py-2 rounded-lg font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50 transition-all flex items-center gap-2"
      >
        <svg 
          class="w-4 h-4" 
          :class="{ 'animate-spin': isCheckingPending }"
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Refresh
      </button>
    </div>

    <!-- Pending Data Summary -->
    <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h3 class="text-lg font-semibold text-slate-800 mb-4">Pending Local Data</h3>
      
      <div v-if="isCheckingPending" class="text-slate-500">
        Checking for pending data...
      </div>
      
      <div v-else-if="!hasPendingData" class="text-center py-8">
        <div class="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <p class="text-slate-600 font-medium">All synced!</p>
        <p class="text-slate-500 text-sm mt-1">No pending data to upload</p>
      </div>
      
      <div v-else class="space-y-4">
        <div class="grid grid-cols-3 gap-4">
          <div class="bg-slate-50 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-slate-800">{{ pendingData?.totalCount }}</div>
            <div class="text-sm text-slate-500">Scores</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-slate-800">{{ pendingData?.competitionIds?.length }}</div>
            <div class="text-sm text-slate-500">Competitions</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-4 text-center">
            <div class="text-3xl font-bold text-amber-600">Pending</div>
            <div class="text-sm text-slate-500">Status</div>
          </div>
        </div>
        
        <p class="text-sm text-slate-600">
          These scores are stored locally and have not been uploaded to the cloud server.
        </p>
      </div>
    </div>

    <!-- Sync Configuration -->
    <div v-if="hasPendingData" class="bg-white rounded-xl shadow-lg border border-slate-200 p-6">
      <h3 class="text-lg font-semibold text-slate-800 mb-4">Cloud Server</h3>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">Server URL</label>
          <input
            v-model="cloudServerUrl"
            type="url"
            placeholder="https://openfeis.org"
            class="w-full px-4 py-3 rounded-lg border border-slate-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
            :disabled="isSyncing"
          />
          <p class="text-xs text-slate-500 mt-1">
            Enter the URL of your Open Feis cloud server
          </p>
        </div>
        
        <button
          @click="startSync"
          :disabled="isSyncing || !cloudServerUrl"
          class="w-full px-6 py-3 rounded-lg font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          <svg v-if="!isSyncing" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ isSyncing ? 'Syncing...' : 'Start Sync' }}
        </button>
      </div>
    </div>

    <!-- Progress Display -->
    <div 
      v-if="progress.phase !== 'idle'"
      class="bg-white rounded-xl shadow-lg border border-slate-200 p-6"
    >
      <h3 class="text-lg font-semibold text-slate-800 mb-4">Sync Progress</h3>
      
      <!-- Progress Bar -->
      <div class="mb-4">
        <div class="flex justify-between text-sm text-slate-600 mb-2">
          <span>{{ progress.message }}</span>
          <span v-if="progress.total > 0">{{ progressPercent }}%</span>
        </div>
        <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
          <div 
            class="h-full rounded-full transition-all duration-300"
            :class="{
              'bg-blue-500': statusColor === 'blue',
              'bg-emerald-500': statusColor === 'emerald',
              'bg-amber-500': statusColor === 'amber',
              'bg-red-500': statusColor === 'red',
              'bg-slate-400': statusColor === 'slate',
            }"
            :style="{ width: `${progressPercent}%` }"
          ></div>
        </div>
      </div>
      
      <!-- Status Badge -->
      <div class="flex items-center gap-3">
        <span 
          :class="[
            'px-3 py-1 rounded-full text-sm font-medium',
            {
              'bg-blue-100 text-blue-800': progress.phase === 'uploading' || progress.phase === 'verifying',
              'bg-slate-100 text-slate-800': progress.phase === 'preparing' || progress.phase === 'idle',
              'bg-emerald-100 text-emerald-800': progress.phase === 'complete' && lastSyncResult?.success,
              'bg-amber-100 text-amber-800': progress.phase === 'complete' && !lastSyncResult?.success,
              'bg-red-100 text-red-800': progress.phase === 'error',
            }
          ]"
        >
          {{ progress.phase.charAt(0).toUpperCase() + progress.phase.slice(1) }}
        </span>
        
        <button
          v-if="progress.phase === 'complete' || progress.phase === 'error'"
          @click="resetSync"
          class="text-sm text-slate-500 hover:text-slate-700"
        >
          Reset
        </button>
      </div>
    </div>

    <!-- Sync Results -->
    <div 
      v-if="lastSyncResult"
      class="bg-white rounded-xl shadow-lg border border-slate-200 p-6"
    >
      <h3 class="text-lg font-semibold text-slate-800 mb-4">Sync Results</h3>
      
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div class="bg-emerald-50 rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-emerald-600">{{ lastSyncResult.uploaded }}</div>
          <div class="text-sm text-emerald-700">Uploaded</div>
        </div>
        <div class="bg-red-50 rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-red-600">{{ lastSyncResult.failed }}</div>
          <div class="text-sm text-red-700">Failed</div>
        </div>
        <div class="bg-amber-50 rounded-lg p-4 text-center">
          <div class="text-2xl font-bold text-amber-600">{{ lastSyncResult.conflicts.length }}</div>
          <div class="text-sm text-amber-700">Conflicts</div>
        </div>
      </div>
      
      <!-- Conflicts Section -->
      <div v-if="hasConflicts" class="mt-6">
        <button
          @click="showConflicts = !showConflicts"
          class="flex items-center gap-2 text-amber-700 hover:text-amber-800 font-medium"
        >
          <svg 
            class="w-4 h-4 transition-transform"
            :class="{ 'rotate-90': showConflicts }"
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
          {{ showConflicts ? 'Hide' : 'Show' }} Conflicts ({{ lastSyncResult.conflicts.length }})
        </button>
        
        <div v-if="showConflicts" class="mt-4 space-y-3">
          <div 
            v-for="conflict in lastSyncResult.conflicts"
            :key="conflict.score_id"
            class="border border-amber-200 rounded-lg p-4 bg-amber-50"
          >
            <div class="flex justify-between items-start mb-3">
              <div>
                <p class="font-medium text-slate-800">Entry: {{ conflict.entry_id.slice(0, 8) }}...</p>
                <p class="text-sm text-slate-600">Competition: {{ conflict.competition_id.slice(0, 8) }}...</p>
              </div>
              <div class="flex gap-2">
                <button
                  @click="resolveConflict(conflict, 'use_local')"
                  class="px-3 py-1.5 text-sm rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                >
                  Use Local
                </button>
                <button
                  @click="resolveConflict(conflict, 'use_server')"
                  class="px-3 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  Keep Server
                </button>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span class="text-slate-500">Local:</span>
                <span class="font-mono font-medium text-blue-700 ml-2">{{ conflict.local_value }}</span>
              </div>
              <div>
                <span class="text-slate-500">Server:</span>
                <span class="font-mono font-medium text-slate-700 ml-2">{{ conflict.server_value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Instructions -->
    <div class="bg-blue-50 border border-blue-200 rounded-xl p-6">
      <h3 class="text-lg font-semibold text-blue-800 mb-3">How Cloud Sync Works</h3>
      <ol class="space-y-2 text-blue-700 text-sm list-decimal list-inside">
        <li>During a feis, scores are saved locally on each judge's device</li>
        <li>When the feis ends and you have internet, enter your cloud server URL</li>
        <li>Click "Start Sync" to upload all local scores to the cloud</li>
        <li>If conflicts are detected (same score with different values), resolve them manually</li>
        <li>Once synced, results become available on the public website</li>
      </ol>
    </div>
  </div>
</template>

