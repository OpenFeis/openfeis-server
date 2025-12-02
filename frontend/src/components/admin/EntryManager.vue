<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';

interface Entry {
  id: string;
  dancer_id: string;
  dancer_name: string;
  dancer_school?: string;
  competition_id: string;
  competition_name: string;
  competitor_number?: number;
  paid: boolean;
}

const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const emit = defineEmits<{
  (e: 'back'): void;
}>();

// State
const entries = ref<Entry[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);

// Filters
const filterPaid = ref<'all' | 'paid' | 'unpaid'>('all');
const filterNumbered = ref<'all' | 'numbered' | 'unnumbered'>('all');
const searchQuery = ref('');

// Bulk number assignment
const startNumber = ref(100);
const isAssigning = ref(false);

// Filtered entries
const filteredEntries = computed(() => {
  let result = entries.value;
  
  // Payment filter
  if (filterPaid.value === 'paid') {
    result = result.filter(e => e.paid);
  } else if (filterPaid.value === 'unpaid') {
    result = result.filter(e => !e.paid);
  }
  
  // Number filter
  if (filterNumbered.value === 'numbered') {
    result = result.filter(e => e.competitor_number !== null);
  } else if (filterNumbered.value === 'unnumbered') {
    result = result.filter(e => e.competitor_number === null);
  }
  
  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(e => 
      e.dancer_name.toLowerCase().includes(query) ||
      e.competition_name.toLowerCase().includes(query) ||
      (e.competitor_number && e.competitor_number.toString().includes(query))
    );
  }
  
  return result;
});

// Group entries by dancer
const entriesByDancer = computed(() => {
  const groups: Record<string, { dancer_name: string; number?: number; entries: Entry[] }> = {};
  
  for (const entry of filteredEntries.value) {
    if (!groups[entry.dancer_id]) {
      groups[entry.dancer_id] = {
        dancer_name: entry.dancer_name,
        number: entry.competitor_number,
        entries: []
      };
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const group = groups[entry.dancer_id]!;
    group.entries.push(entry);
    // Update number if this entry has one
    if (entry.competitor_number) {
      group.number = entry.competitor_number;
    }
  }
  
  return Object.entries(groups).sort((a, b) => {
    // Sort by number if available, then by name
    if (a[1].number && b[1].number) return a[1].number - b[1].number;
    if (a[1].number) return -1;
    if (b[1].number) return 1;
    return a[1].dancer_name.localeCompare(b[1].dancer_name);
  });
});

// Stats
const stats = computed(() => ({
  total: entries.value.length,
  paid: entries.value.filter(e => e.paid).length,
  unpaid: entries.value.filter(e => !e.paid).length,
  numbered: entries.value.filter(e => e.competitor_number !== null).length,
  unnumbered: entries.value.filter(e => e.competitor_number === null).length,
  uniqueDancers: new Set(entries.value.map(e => e.dancer_id)).size
}));

// Fetch entries
const fetchEntries = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`/api/v1/feis/${props.feisId}/entries`);
    if (!response.ok) throw new Error('Failed to fetch entries');
    entries.value = await response.json();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};

// Toggle paid status
const togglePaid = async (entry: Entry) => {
  try {
    const response = await fetch(`/api/v1/entries/${entry.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paid: !entry.paid })
    });
    if (!response.ok) throw new Error('Failed to update entry');
    
    const updated = await response.json();
    const index = entries.value.findIndex(e => e.id === entry.id);
    if (index !== -1) {
      entries.value[index] = updated;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  }
};

// Assign number to single entry/dancer
const assignNumber = async (entry: Entry, number: number) => {
  try {
    const response = await fetch(`/api/v1/entries/${entry.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ competitor_number: number })
    });
    if (!response.ok) throw new Error('Failed to assign number');
    
    const updated = await response.json();
    const index = entries.value.findIndex(e => e.id === entry.id);
    if (index !== -1) {
      entries.value[index] = updated;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  }
};

// Bulk assign numbers
const bulkAssignNumbers = async () => {
  isAssigning.value = true;
  error.value = null;
  successMessage.value = null;
  
  try {
    const response = await fetch(`/api/v1/feis/${props.feisId}/assign-numbers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        feis_id: props.feisId,
        start_number: startNumber.value 
      })
    });
    if (!response.ok) throw new Error('Failed to assign numbers');
    
    const result = await response.json();
    successMessage.value = result.message;
    
    // Refresh entries
    await fetchEntries();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    isAssigning.value = false;
  }
};

// Clear messages after a delay
watch([successMessage, error], () => {
  if (successMessage.value) {
    setTimeout(() => successMessage.value = null, 5000);
  }
});

onMounted(() => {
  fetchEntries();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <button
          @click="emit('back')"
          class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Feis List
        </button>
        <h2 class="text-2xl font-bold text-slate-800">{{ feisName }}</h2>
        <p class="text-slate-600">Manage registrations and competitor numbers</p>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
      {{ error }}
    </div>
    <div v-if="successMessage" class="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg">
      {{ successMessage }}
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-slate-800">{{ stats.uniqueDancers }}</div>
        <div class="text-slate-600 text-sm">Dancers</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-slate-800">{{ stats.total }}</div>
        <div class="text-slate-600 text-sm">Entries</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-emerald-600">{{ stats.paid }}</div>
        <div class="text-slate-600 text-sm">Paid</div>
      </div>
      <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
        <div class="text-3xl font-bold text-amber-600">{{ stats.unpaid }}</div>
        <div class="text-slate-600 text-sm">Unpaid</div>
      </div>
    </div>

    <!-- Bulk Actions -->
    <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
      <h3 class="font-semibold text-slate-800 mb-3">Bulk Assign Numbers</h3>
      <div class="flex items-end gap-4">
        <div>
          <label class="block text-sm text-slate-600 mb-1">Start Number</label>
          <input
            v-model.number="startNumber"
            type="number"
            min="1"
            class="w-32 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <button
          @click="bulkAssignNumbers"
          :disabled="isAssigning || stats.unnumbered === 0"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="isAssigning">Assigning...</span>
          <span v-else>Assign to {{ stats.unnumbered }} Dancers</span>
        </button>
      </div>
      <p class="text-slate-500 text-sm mt-2">
        This will assign numbers {{ startNumber }} onwards to all dancers without numbers.
      </p>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow p-4 border border-slate-200">
      <div class="flex flex-wrap gap-4 items-center">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search by name, competition, or number..."
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        
        <div class="flex gap-2">
          <select
            v-model="filterPaid"
            class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
          >
            <option value="all">All Payments</option>
            <option value="paid">Paid Only</option>
            <option value="unpaid">Unpaid Only</option>
          </select>
          
          <select
            v-model="filterNumbered"
            class="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500"
          >
            <option value="all">All Numbers</option>
            <option value="numbered">Has Number</option>
            <option value="unnumbered">No Number</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-4 border-emerald-200 border-t-emerald-600"></div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="entries.length === 0"
      class="bg-white rounded-xl shadow p-12 text-center border border-slate-200"
    >
      <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Registrations Yet</h3>
      <p class="text-slate-500">Registrations will appear here once dancers sign up.</p>
    </div>

    <!-- Entry List (Grouped by Dancer) -->
    <div v-else class="space-y-4">
      <div
        v-for="[dancerId, group] in entriesByDancer"
        :key="dancerId"
        class="bg-white rounded-xl shadow border border-slate-200 overflow-hidden"
      >
        <!-- Dancer Header -->
        <div class="bg-slate-50 px-4 py-3 flex items-center justify-between border-b border-slate-200">
          <div class="flex items-center gap-3">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white"
              :class="group.number ? 'bg-emerald-500' : 'bg-slate-400'"
            >
              {{ group.number || '?' }}
            </div>
            <div>
              <div class="font-semibold text-slate-800">{{ group.dancer_name }}</div>
              <div class="text-sm text-slate-500">{{ group.entries.length }} competition(s)</div>
            </div>
          </div>
          
          <!-- Quick number input -->
          <div v-if="!group.number" class="flex items-center gap-2">
            <input
              type="number"
              placeholder="#"
              min="1"
              class="w-20 px-2 py-1 text-sm border border-slate-300 rounded"
              @keyup.enter="(e) => group.entries[0] && assignNumber(group.entries[0], parseInt((e.target as HTMLInputElement).value))"
            />
          </div>
        </div>
        
        <!-- Entries -->
        <div class="divide-y divide-slate-100">
          <div
            v-for="entry in group.entries"
            :key="entry.id"
            class="px-4 py-3 flex items-center justify-between hover:bg-slate-50"
          >
            <div>
              <div class="font-medium text-slate-700">{{ entry.competition_name }}</div>
            </div>
            <button
              @click="togglePaid(entry)"
              :class="[
                'px-3 py-1 rounded-full text-sm font-medium transition-colors',
                entry.paid
                  ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                  : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              ]"
            >
              {{ entry.paid ? '✓ Paid' : 'Unpaid' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- No Results -->
    <div 
      v-if="entries.length > 0 && filteredEntries.length === 0"
      class="bg-white rounded-xl shadow p-8 text-center border border-slate-200"
    >
      <p class="text-slate-500">No entries match your filters.</p>
    </div>
  </div>
</template>

