<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { 
  Stage, 
  ScheduledCompetition, 
  ScheduleConflict, 
  SchedulerViewResponse,
  CompetitionLevel,
  DanceType
} from '../../models/types';
import { DANCE_TYPE_INFO } from '../../models/types';
import { useAuthStore } from '../../stores/auth';

// Props
const props = defineProps<{
  feisId: string;
  feisName?: string;
}>();

const emit = defineEmits<{
  (e: 'saved'): void;
}>();

// State
const auth = useAuthStore();
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);

const stages = ref<Stage[]>([]);
const competitions = ref<ScheduledCompetition[]>([]);
const conflicts = ref<ScheduleConflict[]>([]);
const feisDate = ref<string>('');

// Stage management
const showStageModal = ref(false);
const editingStage = ref<Stage | null>(null);
const stageForm = ref({ name: '', color: '#6366f1' });

// Drag and drop state
const draggedComp = ref<ScheduledCompetition | null>(null);
const dragOverStage = ref<string | null>(null);
const dragOverTime = ref<number | null>(null);

// Timeline configuration
const startHour = ref(8); // 8 AM
const endHour = ref(20); // 8 PM
const pixelsPerMinute = ref(2); // Scale factor

// Unscheduled competitions (no stage or time)
const unscheduledComps = computed(() => {
  return competitions.value.filter(c => !c.stage_id || !c.scheduled_time);
});

// Scheduled competitions grouped by stage
const scheduledByStage = computed(() => {
  const grouped: Record<string, ScheduledCompetition[]> = {};
  for (const stage of stages.value) {
    grouped[stage.id] = competitions.value.filter(
      c => c.stage_id === stage.id && c.scheduled_time
    ).sort((a, b) => {
      if (!a.scheduled_time || !b.scheduled_time) return 0;
      return new Date(a.scheduled_time).getTime() - new Date(b.scheduled_time).getTime();
    });
  }
  return grouped;
});

// Calculate total timeline width
const timelineWidth = computed(() => {
  return (endHour.value - startHour.value) * 60 * pixelsPerMinute.value;
});

// Hour markers for timeline
const hourMarkers = computed(() => {
  const markers: { hour: number; label: string; position: number }[] = [];
  for (let h = startHour.value; h <= endHour.value; h++) {
    const label = h <= 12 ? `${h}AM` : h === 12 ? '12PM' : `${h - 12}PM`;
    markers.push({
      hour: h,
      label: h === 12 ? '12PM' : label.replace('0AM', '12AM'),
      position: (h - startHour.value) * 60 * pixelsPerMinute.value
    });
  }
  return markers;
});

// Fetch scheduler data
const loadSchedulerData = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/scheduler`);
    if (!response.ok) {
      throw new Error('Failed to load scheduler data');
    }
    
    const data: SchedulerViewResponse = await response.json();
    stages.value = data.stages;
    competitions.value = data.competitions;
    conflicts.value = data.conflicts;
    feisDate.value = data.feis_date;
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load data';
  } finally {
    loading.value = false;
  }
};

// Create or update a stage
const saveStage = async () => {
  try {
    if (editingStage.value) {
      // Update existing stage
      const response = await auth.authFetch(`/api/v1/stages/${editingStage.value.id}`, {
        method: 'PUT',
        body: JSON.stringify(stageForm.value),
      });
      if (!response.ok) throw new Error('Failed to update stage');
    } else {
      // Create new stage
      const response = await auth.authFetch('/api/v1/stages', {
        method: 'POST',
        body: JSON.stringify({
          feis_id: props.feisId,
          ...stageForm.value,
          sequence: stages.value.length
        }),
      });
      if (!response.ok) throw new Error('Failed to create stage');
    }
    
    showStageModal.value = false;
    await loadSchedulerData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save stage';
  }
};

// Delete a stage
const deleteStage = async (stage: Stage) => {
  if (!confirm(`Delete stage "${stage.name}"? Competitions assigned to this stage will be unassigned.`)) {
    return;
  }
  
  try {
    const response = await auth.authFetch(`/api/v1/stages/${stage.id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete stage');
    await loadSchedulerData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete stage';
  }
};

// Open stage modal for editing
const openStageModal = (stage?: Stage) => {
  editingStage.value = stage || null;
  stageForm.value = stage 
    ? { name: stage.name, color: stage.color || '#6366f1' }
    : { name: '', color: '#6366f1' };
  showStageModal.value = true;
};

// Drag and drop handlers
const onDragStart = (comp: ScheduledCompetition, event: DragEvent) => {
  draggedComp.value = comp;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', comp.id);
  }
};

const onDragOver = (stageId: string, event: DragEvent) => {
  event.preventDefault();
  dragOverStage.value = stageId;
  
  // Calculate time based on mouse position
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const minutes = Math.floor(x / pixelsPerMinute.value);
  dragOverTime.value = minutes;
};

const onDragLeave = () => {
  dragOverStage.value = null;
  dragOverTime.value = null;
};

const onDrop = async (stageId: string, event: DragEvent) => {
  event.preventDefault();
  
  if (!draggedComp.value || dragOverTime.value === null) {
    dragOverStage.value = null;
    dragOverTime.value = null;
    return;
  }
  
  // Calculate scheduled time
  const baseDate = new Date(feisDate.value);
  baseDate.setHours(startHour.value, 0, 0, 0);
  baseDate.setMinutes(baseDate.getMinutes() + dragOverTime.value);
  
  // Update local state optimistically
  const existing = competitions.value.find(c => c.id === draggedComp.value!.id);
  if (existing) {
    const compIndex = competitions.value.indexOf(existing);
    competitions.value[compIndex] = {
      id: existing.id,
      name: existing.name,
      estimated_duration_minutes: existing.estimated_duration_minutes,
      entry_count: existing.entry_count,
      level: existing.level,
      has_conflicts: existing.has_conflicts,
      dance_type: existing.dance_type,
      stage_id: stageId,
      stage_name: stages.value.find(s => s.id === stageId)?.name,
      scheduled_time: baseDate.toISOString()
    };
  }
  
  draggedComp.value = null;
  dragOverStage.value = null;
  dragOverTime.value = null;
};

const onDragEnd = () => {
  draggedComp.value = null;
  dragOverStage.value = null;
  dragOverTime.value = null;
};

// Calculate block position and width for a competition
const getBlockStyle = (comp: ScheduledCompetition) => {
  if (!comp.scheduled_time) return {};
  
  const compDate = new Date(comp.scheduled_time);
  const minutes = (compDate.getHours() - startHour.value) * 60 + compDate.getMinutes();
  const left = minutes * pixelsPerMinute.value;
  const width = comp.estimated_duration_minutes * pixelsPerMinute.value;
  
  return {
    left: `${left}px`,
    width: `${Math.max(width, 40)}px`
  };
};

// Save all changes to the server
const saveSchedule = async () => {
  saving.value = true;
  error.value = null;
  
  try {
    const schedules = competitions.value
      .filter(c => c.stage_id && c.scheduled_time)
      .map(c => ({
        competition_id: c.id,
        stage_id: c.stage_id!,
        scheduled_time: c.scheduled_time!
      }));
    
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/schedule/bulk`, {
      method: 'POST',
      body: JSON.stringify({ schedules }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to save schedule');
    }
    
    const result = await response.json();
    conflicts.value = result.conflicts;
    
    emit('saved');
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save schedule';
  } finally {
    saving.value = false;
  }
};

// Remove a competition from the schedule
const unscheduleCompetition = (comp: ScheduledCompetition) => {
  const existing = competitions.value.find(c => c.id === comp.id);
  if (existing) {
    const index = competitions.value.indexOf(existing);
    competitions.value[index] = {
      id: existing.id,
      name: existing.name,
      estimated_duration_minutes: existing.estimated_duration_minutes,
      entry_count: existing.entry_count,
      level: existing.level,
      has_conflicts: existing.has_conflicts,
      dance_type: existing.dance_type,
      stage_id: undefined,
      stage_name: undefined,
      scheduled_time: undefined
    };
  }
};

// Get level color
const getLevelColor = (level: CompetitionLevel): string => {
  const colors: Record<CompetitionLevel, string> = {
    beginner: 'bg-emerald-500',
    novice: 'bg-blue-500',
    prizewinner: 'bg-amber-500',
    championship: 'bg-purple-500'
  };
  return colors[level] || 'bg-slate-500';
};

// Get dance type icon
const getDanceIcon = (danceType?: DanceType): string => {
  if (!danceType) return '🎵';
  return DANCE_TYPE_INFO[danceType]?.icon || '🎵';
};

// Stage colors
const stageColors = [
  '#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6',
  '#06b6d4', '#f43f5e', '#22c55e', '#3b82f6', '#a855f7'
];

onMounted(() => {
  loadSchedulerData();
});

watch(() => props.feisId, () => {
  loadSchedulerData();
});
</script>

<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-5">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Schedule Builder
          </h2>
          <p class="text-violet-100 text-sm mt-1">
            Drag competitions to stages to build your schedule
          </p>
        </div>
        
        <div class="flex items-center gap-3">
          <button
            @click="openStageModal()"
            class="px-4 py-2 bg-white/20 hover:bg-white/30 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Add Stage
          </button>
          
          <button
            @click="saveSchedule"
            :disabled="saving"
            class="px-4 py-2 bg-white text-indigo-600 hover:bg-indigo-50 rounded-lg font-bold transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <template v-if="saving">
              <div class="animate-spin rounded-full h-4 w-4 border-2 border-indigo-600 border-t-transparent"></div>
              Saving...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              Save Schedule
            </template>
          </button>
        </div>
      </div>
    </div>

    <!-- Error Message -->
    <div v-if="error" class="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center gap-2">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ error }}
    </div>

    <!-- Conflicts Warning -->
    <div v-if="conflicts.length > 0" class="mx-6 mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl">
      <div class="flex items-center gap-2 text-amber-700 font-semibold mb-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        {{ conflicts.length }} Conflict(s) Detected
      </div>
      <ul class="text-sm text-amber-600 space-y-1">
        <li v-for="(conflict, idx) in conflicts.slice(0, 3)" :key="idx" class="flex items-center gap-2">
          <span :class="conflict.severity === 'error' ? 'text-red-600' : ''">
            {{ conflict.severity === 'error' ? '🚫' : '⚠️' }}
          </span>
          {{ conflict.message }}
        </li>
        <li v-if="conflicts.length > 3" class="text-amber-500 italic">
          ... and {{ conflicts.length - 3 }} more
        </li>
      </ul>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="p-12 flex items-center justify-center">
      <div class="animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent"></div>
    </div>

    <div v-else class="p-6">
      <!-- No Stages Message -->
      <div v-if="stages.length === 0" class="text-center py-12">
        <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-indigo-100 flex items-center justify-center">
          <svg class="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No Stages Created</h3>
        <p class="text-slate-500 mb-4">Create stages first to start scheduling competitions.</p>
        <button
          @click="openStageModal()"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
        >
          Create First Stage
        </button>
      </div>

      <!-- Gantt View -->
      <div v-else class="space-y-6">
        <!-- Timeline Header -->
        <div class="relative ml-32 overflow-x-auto">
          <div class="flex border-b border-slate-200 pb-2" :style="{ width: `${timelineWidth}px` }">
            <div
              v-for="marker in hourMarkers"
              :key="marker.hour"
              class="absolute text-xs font-medium text-slate-500"
              :style="{ left: `${marker.position}px` }"
            >
              {{ marker.label }}
            </div>
          </div>
        </div>

        <!-- Stages with timelines -->
        <div class="space-y-4">
          <div
            v-for="stage in stages"
            :key="stage.id"
            class="flex items-stretch"
          >
            <!-- Stage Label -->
            <div 
              class="w-32 flex-shrink-0 rounded-l-xl p-3 flex flex-col justify-center"
              :style="{ backgroundColor: stage.color || '#6366f1' }"
            >
              <div class="font-bold text-white truncate">{{ stage.name }}</div>
              <div class="text-white/70 text-xs">{{ scheduledByStage[stage.id]?.length || 0 }} competitions</div>
              <div class="flex gap-1 mt-2">
                <button
                  @click="openStageModal(stage)"
                  class="p-1 bg-white/20 hover:bg-white/30 rounded text-white"
                  title="Edit stage"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
                <button
                  @click="deleteStage(stage)"
                  class="p-1 bg-white/20 hover:bg-red-500/50 rounded text-white"
                  title="Delete stage"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Timeline Area -->
            <div
              class="flex-1 relative bg-slate-50 rounded-r-xl min-h-[80px] overflow-x-auto border border-l-0 border-slate-200"
              :class="{ 'bg-indigo-50 border-indigo-300': dragOverStage === stage.id }"
              @dragover="onDragOver(stage.id, $event)"
              @dragleave="onDragLeave"
              @drop="onDrop(stage.id, $event)"
            >
              <div :style="{ width: `${timelineWidth}px`, minHeight: '80px' }" class="relative">
                <!-- Hour grid lines -->
                <div
                  v-for="marker in hourMarkers"
                  :key="marker.hour"
                  class="absolute top-0 bottom-0 border-l border-slate-200"
                  :style="{ left: `${marker.position}px` }"
                ></div>

                <!-- Scheduled competitions -->
                <div
                  v-for="comp in scheduledByStage[stage.id]"
                  :key="comp.id"
                  class="absolute top-2 h-14 rounded-lg shadow-md cursor-move flex items-center px-2 gap-1 text-white text-sm font-medium overflow-hidden"
                  :class="[getLevelColor(comp.level), { 'ring-2 ring-red-500': comp.has_conflicts }]"
                  :style="getBlockStyle(comp)"
                  draggable="true"
                  @dragstart="onDragStart(comp, $event)"
                  @dragend="onDragEnd"
                >
                  <span class="text-lg flex-shrink-0">{{ getDanceIcon(comp.dance_type) }}</span>
                  <span class="truncate">{{ comp.name }}</span>
                  <button
                    @click.stop="unscheduleCompetition(comp)"
                    class="ml-auto p-1 hover:bg-white/20 rounded flex-shrink-0"
                    title="Remove from schedule"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <!-- Drop indicator -->
                <div
                  v-if="dragOverStage === stage.id && dragOverTime !== null"
                  class="absolute top-2 h-14 bg-indigo-300/50 rounded-lg border-2 border-dashed border-indigo-500"
                  :style="{ 
                    left: `${dragOverTime * pixelsPerMinute}px`, 
                    width: `${(draggedComp?.estimated_duration_minutes || 30) * pixelsPerMinute}px` 
                  }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Unscheduled Competitions -->
        <div v-if="unscheduledComps.length > 0" class="mt-8">
          <h3 class="text-lg font-bold text-slate-700 mb-4 flex items-center gap-2">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Unscheduled Competitions ({{ unscheduledComps.length }})
          </h3>
          <div class="flex flex-wrap gap-2">
            <div
              v-for="comp in unscheduledComps"
              :key="comp.id"
              class="px-3 py-2 rounded-lg text-white text-sm font-medium cursor-move flex items-center gap-2 shadow-md hover:shadow-lg transition-shadow"
              :class="[getLevelColor(comp.level), { 'ring-2 ring-red-500': comp.has_conflicts }]"
              draggable="true"
              @dragstart="onDragStart(comp, $event)"
              @dragend="onDragEnd"
            >
              <span class="text-lg">{{ getDanceIcon(comp.dance_type) }}</span>
              <span>{{ comp.name }}</span>
              <span class="text-white/70 text-xs">({{ comp.estimated_duration_minutes }}min)</span>
            </div>
          </div>
        </div>

        <!-- Legend -->
        <div class="mt-8 pt-4 border-t border-slate-200">
          <h4 class="text-sm font-semibold text-slate-600 mb-3">Level Colors</h4>
          <div class="flex flex-wrap gap-4">
            <div class="flex items-center gap-2">
              <div class="w-4 h-4 rounded bg-emerald-500"></div>
              <span class="text-sm text-slate-600">Beginner</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-4 h-4 rounded bg-blue-500"></div>
              <span class="text-sm text-slate-600">Novice</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-4 h-4 rounded bg-amber-500"></div>
              <span class="text-sm text-slate-600">Prizewinner</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-4 h-4 rounded bg-purple-500"></div>
              <span class="text-sm text-slate-600">Championship</span>
            </div>
            <div class="flex items-center gap-2 ml-4">
              <div class="w-4 h-4 rounded bg-slate-400 ring-2 ring-red-500"></div>
              <span class="text-sm text-slate-600">Has Conflict</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Stage Modal -->
    <div
      v-if="showStageModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showStageModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-4">
          <h3 class="text-lg font-bold text-white">
            {{ editingStage ? 'Edit Stage' : 'Create Stage' }}
          </h3>
        </div>
        
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Stage Name</label>
            <input
              v-model="stageForm.name"
              type="text"
              placeholder="e.g., Stage A, Main Hall"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all outline-none"
            />
          </div>
          
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Color</label>
            <div class="flex items-center gap-3">
              <input
                v-model="stageForm.color"
                type="color"
                class="w-12 h-12 rounded-lg cursor-pointer border-2 border-slate-200"
              />
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="color in stageColors"
                  :key="color"
                  @click="stageForm.color = color"
                  class="w-8 h-8 rounded-lg border-2 transition-all"
                  :class="stageForm.color === color ? 'border-slate-800 scale-110' : 'border-transparent'"
                  :style="{ backgroundColor: color }"
                ></button>
              </div>
            </div>
          </div>
        </div>
        
        <div class="px-6 py-4 bg-slate-50 flex justify-end gap-3">
          <button
            @click="showStageModal = false"
            class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            @click="saveStage"
            :disabled="!stageForm.name"
            class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ editingStage ? 'Save Changes' : 'Create Stage' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

