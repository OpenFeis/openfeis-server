<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { JudgePanel, FeisAdjudicator } from '../../models/types';

const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const authStore = useAuthStore();

// State
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);

// Data
const panels = ref<JudgePanel[]>([]);
const adjudicators = ref<FeisAdjudicator[]>([]);

// Modal state
const showPanelModal = ref(false);
const editingPanel = ref<JudgePanel | null>(null);

// Form data
const panelForm = ref({
  name: '',
  description: '',
  members: [] as { feis_adjudicator_id: string; sequence: number }[]
});

const API_BASE = '/api/v1';

// Computed
const availableAdjudicators = computed(() => {
  return adjudicators.value.filter(adj => 
    adj.status === 'confirmed' || adj.status === 'active'
  );
});

const isFormValid = computed(() => {
  return panelForm.value.name.trim().length >= 2 && 
         panelForm.value.members.length >= 3;
});

// Fetch panels
async function fetchPanels() {
  loading.value = true;
  error.value = null;
  
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/panels`);
    if (res.ok) {
      const data = await res.json();
      // Handle both null responses and missing panels field
      panels.value = data?.panels || [];
    } else {
      const errorData = await res.json().catch(() => ({}));
      error.value = errorData.detail || 'Failed to load panels';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load panels';
  } finally {
    loading.value = false;
  }
}

// Fetch adjudicators
async function fetchAdjudicators() {
  try {
    const res = await authStore.authFetch(`${API_BASE}/feis/${props.feisId}/adjudicators`);
    if (res.ok) {
      const data = await res.json();
      adjudicators.value = data.adjudicators;
    }
  } catch (err) {
    console.error('Failed to fetch adjudicators:', err);
  }
}

// Open modal for creating new panel
function openCreateModal() {
  editingPanel.value = null;
  panelForm.value = {
    name: '',
    description: '',
    members: []
  };
  showPanelModal.value = true;
}

// Open modal for editing existing panel
function openEditModal(panel: JudgePanel) {
  editingPanel.value = panel;
  panelForm.value = {
    name: panel.name,
    description: panel.description || '',
    members: panel.members.map(m => ({
      feis_adjudicator_id: m.feis_adjudicator_id,
      sequence: m.sequence
    }))
  };
  showPanelModal.value = true;
}

// Add judge to panel
function addJudgeToPanel(adjId: string) {
  // Check if already added
  if (panelForm.value.members.some(m => m.feis_adjudicator_id === adjId)) {
    return;
  }
  
  panelForm.value.members.push({
    feis_adjudicator_id: adjId,
    sequence: panelForm.value.members.length
  });
}

// Remove judge from panel
function removeJudgeFromPanel(adjId: string) {
  panelForm.value.members = panelForm.value.members.filter(
    m => m.feis_adjudicator_id !== adjId
  );
  // Re-sequence
  panelForm.value.members.forEach((m, idx) => {
    m.sequence = idx;
  });
}

// Move judge up/down in sequence
function moveJudge(index: number, direction: 'up' | 'down') {
  const newIndex = direction === 'up' ? index - 1 : index + 1;
  if (newIndex < 0 || newIndex >= panelForm.value.members.length) return;
  
  const temp = panelForm.value.members[index]!;
  panelForm.value.members[index] = panelForm.value.members[newIndex]!;
  panelForm.value.members[newIndex] = temp;
  
  // Update sequences
  panelForm.value.members.forEach((m, idx) => {
    m.sequence = idx;
  });
}

// Save panel
async function savePanel() {
  if (!isFormValid.value) return;
  
  saving.value = true;
  error.value = null;
  successMessage.value = null;
  
  try {
    const url = editingPanel.value
      ? `${API_BASE}/panels/${editingPanel.value.id}`
      : `${API_BASE}/feis/${props.feisId}/panels`;
    
    const method = editingPanel.value ? 'PUT' : 'POST';
    
    const res = await authStore.authFetch(url, {
      method,
      body: JSON.stringify(panelForm.value)
    });
    
    if (res.ok) {
      successMessage.value = editingPanel.value 
        ? 'Panel updated successfully' 
        : 'Panel created successfully';
      showPanelModal.value = false;
      await fetchPanels();
    } else {
      const data = await res.json();
      error.value = data.detail || 'Failed to save panel';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save panel';
  } finally {
    saving.value = false;
  }
}

// Delete panel
async function deletePanel(panel: JudgePanel) {
  if (!confirm(`Delete panel "${panel.name}"? This cannot be undone.`)) {
    return;
  }
  
  try {
    const res = await authStore.authFetch(`${API_BASE}/panels/${panel.id}`, {
      method: 'DELETE'
    });
    
    if (res.ok) {
      successMessage.value = 'Panel deleted successfully';
      await fetchPanels();
    } else {
      const data = await res.json();
      error.value = data.detail || 'Failed to delete panel';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete panel';
  }
}

// Get adjudicator name by ID
function getAdjudicatorName(adjId: string): string {
  const adj = adjudicators.value.find(a => a.id === adjId);
  return adj ? adj.name : 'Unknown';
}

onMounted(async () => {
  await Promise.all([fetchPanels(), fetchAdjudicators()]);
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-lg font-bold text-slate-800">Judge Panels</h3>
        <p class="text-sm text-slate-600 mt-1">
          Create and manage multi-judge panels for championships and ping-pong judging
        </p>
      </div>
      <button
        @click="openCreateModal"
        class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Create Panel
      </button>
    </div>

    <!-- Success Message -->
    <div v-if="successMessage" class="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 flex items-center gap-2">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ successMessage }}
    </div>

    <!-- Error Message -->
    <div v-if="error" class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center gap-2">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ error }}
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-4 border-emerald-600 border-t-transparent"></div>
    </div>

    <!-- Panels List -->
    <div v-else-if="panels.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="panel in panels"
        :key="panel.id"
        class="bg-white rounded-xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between mb-4">
          <div class="flex-1">
            <h4 class="text-lg font-bold text-slate-800">{{ panel.name }}</h4>
            <p v-if="panel.description" class="text-sm text-slate-600 mt-1">{{ panel.description }}</p>
            <div class="flex items-center gap-2 mt-2">
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                {{ panel.member_count }} Judges
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="openEditModal(panel)"
              class="p-2 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-slate-50 transition-colors"
              title="Edit Panel"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click="deletePanel(panel)"
              class="p-2 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-50 transition-colors"
              title="Delete Panel"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Panel Members -->
        <div class="space-y-2">
          <div
            v-for="(member, idx) in panel.members"
            :key="member.id"
            class="flex items-center gap-3 p-3 bg-slate-50 rounded-lg"
          >
            <div class="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-bold">
              {{ idx + 1 }}
            </div>
            <div class="flex-1">
              <div class="font-medium text-slate-800">{{ member.adjudicator_name }}</div>
              <div v-if="member.credential" class="text-xs text-slate-500">{{ member.credential }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-12">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-100 flex items-center justify-center">
        <svg class="w-8 h-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-slate-700 mb-2">No Panels Created Yet</h3>
      <p class="text-slate-500 mb-4">Create a panel to assign multiple judges to stages</p>
      <button
        @click="openCreateModal"
        class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors"
      >
        Create Your First Panel
      </button>
    </div>

    <!-- Create/Edit Panel Modal -->
    <div
      v-if="showPanelModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="showPanelModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <!-- Modal Header -->
        <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4">
          <h3 class="text-lg font-bold text-white">
            {{ editingPanel ? 'Edit Panel' : 'Create Panel' }}
          </h3>
          <p class="text-emerald-100 text-sm mt-1">
            {{ editingPanel ? 'Update panel details and members' : 'Create a new judge panel for championships or ping-pong judging' }}
          </p>
        </div>

        <!-- Modal Body -->
        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <!-- Panel Name -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Panel Name *</label>
            <input
              v-model="panelForm.name"
              type="text"
              placeholder="e.g., Championship Panel A"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Description (Optional)</label>
            <textarea
              v-model="panelForm.description"
              rows="2"
              placeholder="e.g., Primary championship panel for U12+"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none resize-none"
            ></textarea>
          </div>

          <!-- Panel Members -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">
              Panel Members * (minimum 3)
            </label>
            
            <!-- Selected Members -->
            <div v-if="panelForm.members.length > 0" class="space-y-2 mb-4">
              <div
                v-for="(member, idx) in panelForm.members"
                :key="member.feis_adjudicator_id"
                class="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg"
              >
                <div class="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-bold">
                  {{ idx + 1 }}
                </div>
                <div class="flex-1">
                  <div class="font-medium text-slate-800">
                    {{ getAdjudicatorName(member.feis_adjudicator_id) }}
                  </div>
                </div>
                <div class="flex items-center gap-1">
                  <button
                    v-if="idx > 0"
                    @click="moveJudge(idx, 'up')"
                    class="p-1 text-slate-400 hover:text-emerald-600 rounded transition-colors"
                    title="Move Up"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                    </svg>
                  </button>
                  <button
                    v-if="idx < panelForm.members.length - 1"
                    @click="moveJudge(idx, 'down')"
                    class="p-1 text-slate-400 hover:text-emerald-600 rounded transition-colors"
                    title="Move Down"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  <button
                    @click="removeJudgeFromPanel(member.feis_adjudicator_id)"
                    class="p-1 text-slate-400 hover:text-red-600 rounded transition-colors ml-2"
                    title="Remove"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            <!-- Available Adjudicators -->
            <div class="border-2 border-slate-200 rounded-xl p-4 max-h-60 overflow-y-auto">
              <p class="text-sm text-slate-600 mb-3">Click to add judges to the panel:</p>
              <div
                v-if="availableAdjudicators.length === 0"
                class="text-center py-4 text-slate-500"
              >
                No confirmed adjudicators available
              </div>
              <div v-else class="space-y-2">
                <button
                  v-for="adj in availableAdjudicators"
                  :key="adj.id"
                  @click="addJudgeToPanel(adj.id)"
                  :disabled="panelForm.members.some(m => m.feis_adjudicator_id === adj.id)"
                  class="w-full text-left p-3 rounded-lg border transition-all"
                  :class="panelForm.members.some(m => m.feis_adjudicator_id === adj.id)
                    ? 'border-slate-200 bg-slate-50 text-slate-400 cursor-not-allowed'
                    : 'border-slate-200 hover:border-emerald-500 hover:bg-emerald-50 cursor-pointer'"
                >
                  <div class="flex items-center justify-between">
                    <div>
                      <div class="font-medium">{{ adj.name }}</div>
                      <div v-if="adj.credential" class="text-xs text-slate-500">{{ adj.credential }}</div>
                    </div>
                    <svg
                      v-if="panelForm.members.some(m => m.feis_adjudicator_id === adj.id)"
                      class="w-5 h-5 text-emerald-600"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </button>
              </div>
            </div>
          </div>

          <!-- Info Box -->
          <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-sm text-emerald-800">
            <div class="flex items-start gap-2">
              <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p class="font-semibold mb-1">About Judge Panels:</p>
                <ul class="space-y-1 text-emerald-700">
                  <li>• Panels can be assigned to one stage (major championships) or multiple stages (ping-pong)</li>
                  <li>• All panel members can score competitions assigned to the panel</li>
                  <li>• Typical panel sizes: 3 judges (most championships) or 5 judges (major events)</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-6 py-4 bg-slate-50 flex justify-end gap-3 border-t border-slate-200">
          <button
            @click="showPanelModal = false"
            class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            @click="savePanel"
            :disabled="!isFormValid || saving"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <div v-if="saving" class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
            {{ saving ? 'Saving...' : (editingPanel ? 'Update Panel' : 'Create Panel') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

