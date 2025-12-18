<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { 
  Stage, 
  ScheduledCompetition, 
  ScheduleConflict, 
  SchedulerViewResponse,
  CompetitionLevel,
  DanceType,
  FeisAdjudicator,
  AdjudicatorListResponse,
  StageJudgeCoverage,
  InstantSchedulerRequest,
  InstantSchedulerResponse,
  JudgePanel
} from '../../models/types';
import { DANCE_TYPE_INFO } from '../../models/types';
import { useAuthStore } from '../../stores/auth';
import CompetitionForm from './CompetitionForm.vue';

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
const showCodes = ref(true);
const sidebarCollapsed = ref(false);
const pixelsPerMinute = ref(5); // Scale factor (Height in vertical view) - Default "M" size

// Initialize sidebar state
const initSidebar = () => {
  const isMobile = window.innerWidth < 768;
  const hasNoUnscheduled = unscheduledComps.value.length === 0;
  sidebarCollapsed.value = isMobile || hasNoUnscheduled;
};

const getZoomLabel = (level: number): string => {
  const labels: Record<number, string> = {
    3: 'XS',
    4: 'S',
    5: 'M',
    6: 'L',
    7: 'XL'
  };
  return labels[level] || '?';
};

const stages = ref<Stage[]>([]);
const competitions = ref<ScheduledCompetition[]>([]);
const conflicts = ref<ScheduleConflict[]>([]);
const feisDate = ref<string>('');

// Adjudicator and panel data
const adjudicators = ref<FeisAdjudicator[]>([]);
const panels = ref<JudgePanel[]>([]);

// Competition editor
const showCompetitionEditor = ref(false);
const editingCompetition = ref<ScheduledCompetition | null>(null);

// Stage management
const showStageModal = ref(false);
const editingStage = ref<Stage | null>(null);
const stageForm = ref({ name: '', color: '#6366f1' });

// Coverage management
const showCoverageModal = ref(false);
const coverageStage = ref<Stage | null>(null);
const coverageForm = ref({
  assignment_type: 'judge' as 'judge' | 'panel', // NEW: Select judge or panel
  feis_adjudicator_id: '',
  panel_id: '', // NEW: For panel assignment
  feis_day: '',
  start_time: '09:00',
  end_time: '12:00',
  note: '',
  selected_stage_ids: [] as string[] // For multi-stage assignment
});

// Instant Scheduler state
const showInstantSchedulerModal = ref(false);
const showInstantSchedulerConfigModal = ref(false);
const instantSchedulerLoading = ref(false);
const instantSchedulerResult = ref<InstantSchedulerResponse | null>(null);
const instantSchedulerConfig = ref<InstantSchedulerRequest>({
  min_comp_size: 5,
  max_comp_size: 25,
  lunch_window_start: '11:00',
  lunch_window_end: '12:00',
  lunch_duration_minutes: 30,
  allow_two_year_merge_up: true,
  strict_no_exhibition: false,
  feis_start_time: '08:00',
  feis_end_time: '17:00',
  clear_existing: true,
  default_grade_duration_minutes: 15,
  default_champ_duration_minutes: 30
});

// Drag and drop state
const draggedComp = ref<ScheduledCompetition | null>(null);
const dragOverStage = ref<string | null>(null);
const dragOverTime = ref<number | null>(null);

// Computed: Current drag time label (e.g., "1:20 PM")
const dragTimeLabel = computed(() => {
  if (dragOverTime.value === null) return '';
  
  const totalMinutes = startHour.value * 60 + dragOverTime.value;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  const displayMinutes = String(minutes).padStart(2, '0');
  
  return `${displayHours}:${displayMinutes} ${period}`;
});

// Timeline configuration
const startHour = ref(8); // 8 AM
const endHour = ref(20); // 8 PM

// Unscheduled competitions (no stage or time)
const unscheduledComps = computed(() => {
  return competitions.value.filter(c => !c.stage_id || !c.scheduled_time);
});

// Calculate total timeline height
const timelineHeight = computed(() => {
  return (endHour.value - startHour.value) * 60 * pixelsPerMinute.value;
});

const columnWidth = 240; // w-60 in pixels

// Find if a coverage block is the "primary" (first) among its merged group
const isPrimaryStageForCoverage = (cov: StageJudgeCoverage, stageId: string) => {
  if (!cov.is_panel || !cov.panel_id) return true;
  
  // Find all stages that have this exact panel assignment at the same time
  const coverageStages = stages.value.filter(s => 
    s.judge_coverage.some(c => 
      c.panel_id === cov.panel_id &&
      c.feis_day === cov.feis_day &&
      c.start_time === cov.start_time &&
      c.end_time === cov.end_time
    )
  ).sort((a, b) => a.sequence - b.sequence);
  
  const firstStage = coverageStages[0];
  return !!firstStage && firstStage.id === stageId;
};

// Calculate how many columns a coverage block should span
const getCoverageSpan = (cov: StageJudgeCoverage) => {
  if (!cov.is_panel || !cov.panel_id) return 1;
  
  const count = stages.value.filter(s => 
    s.judge_coverage.some(c => 
      c.panel_id === cov.panel_id &&
      c.feis_day === cov.feis_day &&
      c.start_time === cov.start_time &&
      c.end_time === cov.end_time
    )
  ).length;
  
  return count;
};

// Find if a competition is currently "merged" due to panel coverage
const getCompetitionMergeInfo = (comp: ScheduledCompetition) => {
  if (!comp.stage_id || !comp.scheduled_time) return { isMerged: false, span: 1, isPrimary: true };
  
  const stage = stages.value.find(s => s.id === comp.stage_id);
  if (!stage) return { isMerged: false, span: 1, isPrimary: true };
  
  const compTime = new Date(comp.scheduled_time);
  const timeStr = `${String(compTime.getHours()).padStart(2, '0')}:${String(compTime.getMinutes()).padStart(2, '0')}`;
  
  // Find coverage that includes this competition's time
  const coverage = stage.judge_coverage.find(cov => {
    return cov.is_panel && cov.panel_id &&
           timeStr >= cov.start_time && timeStr < cov.end_time;
  });
  
  if (!coverage) return { isMerged: false, span: 1, isPrimary: true };
  
  const span = getCoverageSpan(coverage);
  const isPrimary = isPrimaryStageForCoverage(coverage, comp.stage_id);
  
  return { isMerged: span > 1, span, isPrimary, coverage };
};

// All visual coverage blocks across all stages (primary only)
const allVisualCoverage = computed(() => {
  const all: StageJudgeCoverage[] = [];
  stages.value.forEach(stage => {
    stage.judge_coverage.forEach(cov => {
      if (isPrimaryStageForCoverage(cov, stage.id)) {
        all.push(cov);
      }
    });
  });
  return all;
});

// All scheduled competitions across all stages
const allVisualCompetitions = computed(() => {
  return competitions.value.filter(c => c.stage_id && c.scheduled_time);
});

// Hour markers for timeline
const hourMarkers = computed(() => {
  const markers: { hour: number; label: string; position: number }[] = [];
  for (let h = startHour.value; h <= endHour.value; h++) {
    let label: string;
    if (h === 0 || h === 24) {
      label = '12AM';
    } else if (h === 12) {
      label = '12PM';
    } else if (h < 12) {
      label = `${h}AM`;
    } else {
      label = `${h - 12}PM`;
    }
    const position = (h - startHour.value) * 60 * pixelsPerMinute.value;
    markers.push({
      hour: h,
      label,
      position
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
    
    // Auto-collapse sidebar if no unscheduled competitions
    if (competitions.value.filter(c => !c.stage_id || !c.scheduled_time).length === 0) {
      sidebarCollapsed.value = true;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load data';
  } finally {
    loading.value = false;
  }
};

// Fetch adjudicators for assignment dropdown
const loadAdjudicators = async () => {
  try {
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/adjudicators`);
    if (response.ok) {
      const data: AdjudicatorListResponse = await response.json();
      adjudicators.value = data.adjudicators;
    }
  } catch (err) {
    console.error('Failed to load adjudicators:', err);
  }
};

// Fetch panels for assignment dropdown
const loadPanels = async () => {
  try {
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/panels`);
    if (response.ok) {
      const data = await response.json();
      panels.value = data.panels;
    }
  } catch (err) {
    console.error('Failed to load panels:', err);
  }
};

// Open adjudicator assignment modal (Deprecated)
// const openAdjudicatorModal = (comp: ScheduledCompetition) => {
//   // Logic mostly replaced by coverage, but could be used for specific overrides
//   console.log('Adjudicator modal requested for', comp.id);
// };

// Assign adjudicator to competition (Deprecated)
// const assignAdjudicator = async () => {
//   // Logic deprecated
// };

// Open competition editor modal
const openCompetitionEditor = (comp: ScheduledCompetition) => {
  editingCompetition.value = comp;
  showCompetitionEditor.value = true;
};

// Close competition editor
const closeCompetitionEditor = () => {
  showCompetitionEditor.value = false;
  editingCompetition.value = null;
};

// Save competition changes
const saveCompetition = async (payload: any) => {
  if (!editingCompetition.value) return;
  
  try {
    const response = await auth.authFetch(`/api/v1/competitions/${editingCompetition.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to update competition');
    }
    
    closeCompetitionEditor();
    await loadSchedulerData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save competition';
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

// Open coverage modal for a stage
const openCoverageModal = (stage: Stage) => {
  coverageStage.value = stage;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  coverageForm.value = {
    assignment_type: 'judge',
    feis_adjudicator_id: '',
    panel_id: '',
    feis_day: feisDate.value || today,
    start_time: '09:00',
    end_time: '12:00',
    note: '',
    selected_stage_ids: [stage.id] // Pre-select current stage
  };
  showCoverageModal.value = true;
};

// Add coverage block (Multi-stage supported, judge or panel)
const addCoverage = async () => {
  // Validation
  if (coverageForm.value.assignment_type === 'judge' && !coverageForm.value.feis_adjudicator_id) {
    error.value = 'Please select a judge';
    return;
  }
  if (coverageForm.value.assignment_type === 'panel' && !coverageForm.value.panel_id) {
    error.value = 'Please select a panel';
    return;
  }
  if (coverageForm.value.selected_stage_ids.length === 0) {
    error.value = 'Please select at least one stage';
    return;
  }
  
  try {
    const promises = coverageForm.value.selected_stage_ids.map(stageId => {
      const payload: any = {
        feis_day: coverageForm.value.feis_day,
        start_time: coverageForm.value.start_time,
        end_time: coverageForm.value.end_time,
        note: coverageForm.value.note
      };
      
      // Add either judge or panel ID based on assignment type
      if (coverageForm.value.assignment_type === 'judge') {
        payload.feis_adjudicator_id = coverageForm.value.feis_adjudicator_id;
      } else {
        payload.panel_id = coverageForm.value.panel_id;
      }
      
      return auth.authFetch(`/api/v1/stages/${stageId}/coverage`, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    });

    await Promise.all(promises);
    
    showCoverageModal.value = false;
    await loadSchedulerData(); // Refresh to show new coverage
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to add coverage';
  }
};

// Delete coverage block
const deleteCoverage = async (coverage: StageJudgeCoverage) => {
  if (!confirm(`Remove ${coverage.adjudicator_name}'s coverage (${coverage.start_time}-${coverage.end_time})?`)) {
    return;
  }
  
  try {
    const response = await auth.authFetch(`/api/v1/stage-coverage/${coverage.id}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) throw new Error('Failed to delete coverage');
    await loadSchedulerData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete coverage';
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
      scheduled_time: undefined,
      code: existing.code
    };
  }
};
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
  
  // Calculate time based on mouse position (Vertical)
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const y = event.clientY - rect.top + target.scrollTop; // Account for scrolling if any
  
  // Snap to 4-minute grid (15 events per hour)
  const rawMinutes = Math.floor(y / pixelsPerMinute.value);
  const minutes = Math.round(rawMinutes / 4) * 4;
  
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
  
  // Calculate scheduled time using local date parts to avoid timezone shifting
  // feisDate.value is YYYY-MM-DD
  const dateParts = feisDate.value.split('-');
  const year = parseInt(dateParts[0] || '2025');
  const month = parseInt(dateParts[1] || '1') - 1;
  const day = parseInt(dateParts[2] || '1');
  
  const baseDate = new Date(year, month, day);
  baseDate.setHours(startHour.value, 0, 0, 0);
  baseDate.setMinutes(baseDate.getMinutes() + dragOverTime.value);
  
  // Create local ISO string (YYYY-MM-DDTHH:mm:ss) 
  const localIsoString = baseDate.getFullYear() + '-' +
    String(baseDate.getMonth() + 1).padStart(2, '0') + '-' +
    String(baseDate.getDate()).padStart(2, '0') + 'T' +
    String(baseDate.getHours()).padStart(2, '0') + ':' +
    String(baseDate.getMinutes()).padStart(2, '0') + ':00';

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
      scheduled_time: localIsoString,
      code: existing.code
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

// Calculate block position and HEIGHT for a competition (Vertical)
const getBlockStyle = (comp: ScheduledCompetition) => {
  if (!comp.scheduled_time || !comp.stage_id) return {};
  
  const compDate = new Date(comp.scheduled_time);
  const minutes = (compDate.getHours() - startHour.value) * 60 + compDate.getMinutes();
  const top = minutes * pixelsPerMinute.value;
  const height = comp.estimated_duration_minutes * pixelsPerMinute.value;
  
  const mergeInfo = getCompetitionMergeInfo(comp);
  const span = mergeInfo.span;
  const width = span * columnWidth - 8;
  
  // Find the primary stage index for positioning
  let stageIndex = stages.value.findIndex(s => s.id === comp.stage_id);
  if (mergeInfo.isMerged && mergeInfo.coverage) {
      const coverageStages = stages.value.filter(s => 
          s.judge_coverage.some(c => 
            c.panel_id === mergeInfo.coverage!.panel_id &&
            c.feis_day === mergeInfo.coverage!.feis_day &&
            c.start_time === mergeInfo.coverage!.start_time &&
            c.end_time === mergeInfo.coverage!.end_time
          )
      ).sort((a, b) => a.sequence - b.sequence);
      
      const firstStage = coverageStages[0];
      if (firstStage) {
          stageIndex = stages.value.findIndex(s => s.id === firstStage.id);
      }
  }
  
  const left = stageIndex * columnWidth + 4;
  
  return {
    top: `${top}px`,
    left: `${left}px`,
    height: `${Math.max(height, 20)}px`,
    width: `${width}px`,
    zIndex: span > 1 ? 15 : 10
  };
};

// Calculate style for the drag-and-drop preview block
const getDropPreviewStyle = computed(() => {
  if (!dragOverStage.value || dragOverTime.value === null) return {};
  
  const stage = stages.value.find(s => s.id === dragOverStage.value);
  if (!stage) return {};
  
  // Hypothetical competition at this time to check for merged area
  const totalMinutesAtDrag = startHour.value * 60 + dragOverTime.value;
  const h = Math.floor(totalMinutesAtDrag / 60);
  const m = totalMinutesAtDrag % 60;
  const timeStr = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  
  const coverage = stage.judge_coverage.find(cov => {
    return cov.is_panel && cov.panel_id &&
           timeStr >= cov.start_time && timeStr < cov.end_time;
  });
  
  let span = 1;
  let stageIndex = stages.value.findIndex(s => s.id === dragOverStage.value);
  
  if (coverage) {
    span = getCoverageSpan(coverage);
    const coverageStages = stages.value.filter(s => 
      s.judge_coverage.some(c => 
        c.panel_id === coverage.panel_id &&
        c.feis_day === coverage.feis_day &&
        c.start_time === coverage.start_time &&
        c.end_time === coverage.end_time
      )
    ).sort((a, b) => a.sequence - b.sequence);
    
    const firstStage = coverageStages[0];
    if (firstStage) {
      stageIndex = stages.value.findIndex(s => s.id === firstStage.id);
    }
  }
  
  const top = dragOverTime.value * pixelsPerMinute.value;
  const height = (draggedComp.value?.estimated_duration_minutes || 30) * pixelsPerMinute.value;
  const width = span * columnWidth - 8;
  const left = stageIndex * columnWidth + 4;
  
  return {
    top: `${top}px`,
    left: `${left}px`,
    height: `${height}px`,
    width: `${width}px`
  };
});

// Calculate coverage block position and height
const getCoverageStyle = (cov: StageJudgeCoverage) => {
  const startParts = cov.start_time.split(':');
  const endParts = cov.end_time.split(':');
  const startHourNum = parseInt(startParts[0] || '0', 10);
  const startMinNum = parseInt(startParts[1] || '0', 10);
  const endHourNum = parseInt(endParts[0] || '0', 10);
  const endMinNum = parseInt(endParts[1] || '0', 10);
  
  const startMinutes = (startHourNum - startHour.value) * 60 + startMinNum;
  const endMinutes = (endHourNum - startHour.value) * 60 + endMinNum;
  
  const top = startMinutes * pixelsPerMinute.value;
  const height = (endMinutes - startMinutes) * pixelsPerMinute.value;
  
  const span = getCoverageSpan(cov);
  const width = span * columnWidth - 8;
  
  // Find primary stage index
  const coverageStages = stages.value.filter(s => 
    s.judge_coverage.some(c => 
      c.panel_id === cov.panel_id &&
      c.feis_day === cov.feis_day &&
      c.start_time === cov.start_time &&
      c.end_time === cov.end_time
    )
  ).sort((a, b) => a.sequence - b.sequence);
  
  const primaryIndex = stages.value.findIndex(s => s.id === (coverageStages[0]?.id || cov.stage_id));
  const left = primaryIndex * columnWidth + 4;
  
  return {
    top: `${Math.max(top, 0)}px`,
    left: `${left}px`,
    height: `${Math.max(height, 10)}px`,
    width: `${width}px`,
    zIndex: span > 1 ? 5 : 0
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

const getLevelColor = (level: CompetitionLevel): string => {
  const colors: Record<CompetitionLevel, string> = {
    first_feis: 'bg-pink-500',
    beginner_1: 'bg-emerald-500',
    beginner_2: 'bg-teal-500',
    novice: 'bg-blue-500',
    prizewinner: 'bg-amber-500',
    preliminary_championship: 'bg-orange-500',
    open_championship: 'bg-purple-500'
  };
  return colors[level] || 'bg-slate-500';
};

// Get dance type icon
const getDanceIcon = (danceType?: DanceType): string => {
  if (!danceType) return '🎵';
  return DANCE_TYPE_INFO[danceType]?.icon || '🎵';
};

// Find stages covered by the same panel at the same time
// Stage colors
const stageColors = [
  '#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6',
  '#06b6d4', '#f43f5e', '#22c55e', '#3b82f6', '#a855f7'
];

// Run instant scheduler
const runInstantScheduler = async () => {
  instantSchedulerLoading.value = true;
  instantSchedulerResult.value = null;
  error.value = null;
  
  try {
    const response = await auth.authFetch(`/api/v1/feis/${props.feisId}/schedule/instant`, {
      method: 'POST',
      body: JSON.stringify(instantSchedulerConfig.value)
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to run instant scheduler');
    }
    
    const result: InstantSchedulerResponse = await response.json();
    instantSchedulerResult.value = result;
    showInstantSchedulerConfigModal.value = false;
    showInstantSchedulerModal.value = true;
    
    // Reload scheduler data to show new placements
    await loadSchedulerData();
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to run instant scheduler';
  } finally {
    instantSchedulerLoading.value = false;
  }
};

// Open instant scheduler config modal
const openInstantSchedulerConfig = () => {
  showInstantSchedulerConfigModal.value = true;
};

// Close summary modal and refresh
const closeInstantSchedulerSummary = () => {
  showInstantSchedulerModal.value = false;
  instantSchedulerResult.value = null;
};

onMounted(() => {
  loadSchedulerData();
  loadAdjudicators();
  loadPanels();
  initSidebar();
});

watch(() => unscheduledComps.value.length, (newCount) => {
  if (newCount === 0) {
    sidebarCollapsed.value = true;
  }
});

watch(() => props.feisId, () => {
  loadSchedulerData();
});
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-100px)] bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-4 flex-shrink-0 z-20">
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
          <!-- Zoom Controls -->
          <div class="flex flex-col items-center bg-indigo-700/50 rounded-lg p-1 mr-2">
            <span class="text-[10px] font-bold text-indigo-100 leading-none mb-1">ZOOM LEVEL</span>
            <div class="flex items-center gap-1">
              <button 
                @click="pixelsPerMinute = Math.max(3, pixelsPerMinute - 1)"
                class="p-1 text-white hover:bg-white/10 rounded transition-colors leading-none flex items-center justify-center h-6 w-6"
                title="Zoom Out"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
                </svg>
              </button>
              <span class="text-xs font-medium text-white px-1 w-5 text-center">{{ getZoomLabel(pixelsPerMinute) }}</span>
              <button 
                @click="pixelsPerMinute = Math.min(7, pixelsPerMinute + 1)"
                class="p-1 text-white hover:bg-white/10 rounded transition-colors leading-none flex items-center justify-center h-6 w-6"
                title="Zoom In"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
          </div>

          <button
            @click="openInstantSchedulerConfig"
            :disabled="instantSchedulerLoading"
            class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-white rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <template v-if="instantSchedulerLoading">
              <div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
              Generating...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Instant Scheduler
            </template>
          </button>
          
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
    <div v-if="error" class="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center gap-2 flex-shrink-0">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ error }}
    </div>

    <!-- Conflicts Warning -->
    <div v-if="conflicts.length > 0" class="mx-6 mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl flex-shrink-0">
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

    <!-- Main Content (Scrollable) -->
    <div class="flex-1 overflow-hidden flex flex-row relative">
      <!-- Loading State -->
      <div v-if="loading" class="absolute inset-0 z-50 bg-white/80 flex items-center justify-center">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-indigo-600 border-t-transparent"></div>
      </div>

      <!-- No Stages Message -->
      <div v-if="stages.length === 0 && !loading" class="flex-1 flex flex-col items-center justify-center">
        <div class="w-16 h-16 mb-4 rounded-full bg-indigo-100 flex items-center justify-center">
          <svg class="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No Stages Created</h3>
        <button @click="openStageModal()" class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">
          Create First Stage
        </button>
      </div>

      <div v-else class="flex flex-row flex-1 h-full overflow-hidden relative">
        <!-- Sidebar: Unscheduled Competitions -->
        <div 
          v-if="!sidebarCollapsed"
          class="w-72 bg-slate-50 border-r border-slate-200 flex-shrink-0 flex flex-col h-full z-20"
        >
            <div class="p-4 bg-white border-b border-slate-200 flex items-center justify-between">
                <div>
                  <h3 class="font-bold text-slate-700">Unscheduled</h3>
                  <p class="text-xs text-slate-500">{{ unscheduledComps.length }} competitions</p>
                </div>
                <button 
                  @click="sidebarCollapsed = true"
                  class="p-1 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-slate-600 transition-colors"
                  title="Collapse Sidebar"
                >
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                  </svg>
                </button>
            </div>
            <div class="p-4 bg-white border-b border-slate-200">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Display Mode</span>
                  <div class="flex items-center bg-slate-100 rounded-lg p-0.5">
                    <button 
                      @click="showCodes = false"
                      class="px-2 py-1 text-[10px] font-medium rounded-md transition-all"
                      :class="!showCodes ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                    >
                      Names
                    </button>
                    <button 
                      @click="showCodes = true"
                      class="px-2 py-1 text-[10px] font-medium rounded-md transition-all"
                      :class="showCodes ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                    >
                      Codes
                    </button>
                  </div>
                </div>
            </div>
            <div class="flex-1 overflow-y-auto p-2 space-y-2">
                <div
                    v-for="comp in unscheduledComps"
                    :key="comp.id"
                    class="p-2 rounded-lg text-white text-sm font-medium cursor-move shadow-sm hover:shadow-md transition-shadow group relative"
                    :class="[getLevelColor(comp.level), { 'ring-2 ring-red-500': comp.has_conflicts }]"
                    draggable="true"
                    @dragstart="onDragStart(comp, $event)"
                    @dragend="onDragEnd"
                    @dblclick="openCompetitionEditor(comp)"
                >
                    <div class="flex items-center gap-2">
                        <span class="text-lg">{{ getDanceIcon(comp.dance_type) }}</span>
                        <div class="leading-tight">
                            <div class="truncate w-44" :title="comp.name">
                              {{ showCodes && comp.code ? comp.code : comp.name }}
                            </div>
                            <div class="text-white/80 text-xs flex gap-1">
                              <span>{{ comp.estimated_duration_minutes }}m</span>
                              <span v-if="showCodes && comp.code" class="opacity-70 truncate max-w-[100px]">- {{ comp.name }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Floating Sidebar Toggle (When Collapsed) -->
        <button
          v-if="sidebarCollapsed"
          @click="sidebarCollapsed = false"
          class="absolute left-4 top-4 z-40 bg-white border border-slate-200 rounded-full p-2 shadow-lg hover:bg-slate-50 text-indigo-600 transition-all hover:scale-110 flex items-center gap-2 pr-4"
          title="Show Unscheduled"
        >
          <div class="bg-indigo-600 text-white rounded-full p-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </div>
          <span class="text-xs font-bold uppercase tracking-wider">Show Unscheduled</span>
          <span v-if="unscheduledComps.length > 0" class="bg-indigo-100 text-indigo-700 text-[10px] px-1.5 py-0.5 rounded-full">
            {{ unscheduledComps.length }}
          </span>
        </button>

        <!-- Vertical Scheduler Scroll Area -->
        <div class="flex-1 overflow-auto bg-white flex relative">
            
            <!-- Time Column (Sticky) -->
            <div class="sticky left-0 z-50 bg-white border-r border-slate-200 w-16 flex-shrink-0" :style="{ minHeight: `${timelineHeight + 56}px` }">
                <div class="h-14 bg-white border-b border-slate-200 sticky top-0 z-[70]"></div> <!-- Header spacer -->
                <div class="relative" :style="{ height: `${timelineHeight}px` }">
                    <div
                        v-for="marker in hourMarkers"
                        :key="marker.hour"
                        class="absolute right-2 text-xs font-medium text-slate-400"
                        :style="{ top: `${marker.position}px` }"
                    >
                        {{ marker.label }}
                    </div>
                </div>
            </div>

            <!-- Stages Area -->
            <div class="flex flex-col relative" :style="{ minHeight: `${timelineHeight + 56}px` }">
                
                <!-- Sticky Stage Headers Row -->
                <div class="flex sticky top-0 z-[60] bg-white border-b border-slate-200 shadow-sm h-14">
                    <div
                        v-for="stage in stages"
                        :key="'header-' + stage.id"
                        class="w-60 flex-shrink-0 flex items-center justify-between px-3 h-full"
                        :style="{ backgroundColor: stage.color || '#6366f1' }"
                    >
                        <div class="text-white font-bold truncate">{{ stage.name }}</div>
                        <div class="flex items-center gap-1">
                            <button
                                @click="openCoverageModal(stage)"
                                class="p-1 hover:bg-white/20 rounded text-white"
                                title="Add/Edit Judge Coverage"
                            >
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                </svg>
                            </button>
                            <button
                                @click="openStageModal(stage)"
                                class="p-1 hover:bg-white/20 rounded text-white"
                                title="Edit Stage"
                            >
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                            </button>
                            <button
                                @click="deleteStage(stage)"
                                class="p-1 hover:bg-white/20 hover:text-red-200 rounded text-white"
                                title="Delete Stage"
                            >
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Main Content Row -->
                <div class="flex relative">
                    <!-- Background & Drop Zones -->
                    <div
                        v-for="stage in stages"
                        :key="stage.id"
                        class="w-60 flex-shrink-0 border-r border-slate-200 bg-white relative h-full"
                    >
                        <!-- Stage Timeline Lane (Drop Target) -->
                        <div 
                            class="relative"
                            :style="{ height: `${timelineHeight}px` }"
                            :class="{ 'bg-indigo-50/80 ring-2 ring-indigo-300 inset-0': dragOverStage === stage.id }"
                            @dragover="onDragOver(stage.id, $event)"
                            @dragleave="onDragLeave"
                            @drop="onDrop(stage.id, $event)"
                        >
                            <!-- Grid Lines -->
                            <div
                                v-for="marker in hourMarkers"
                                :key="marker.hour"
                                class="absolute left-0 right-0 border-t border-slate-100"
                                :style="{ top: `${marker.position}px` }"
                            ></div>
                        </div>
                    </div>

                    <!-- Shared Content Layer (Visuals) -->
                    <div class="absolute top-0 left-0 right-0 pointer-events-none z-10" :style="{ height: `${timelineHeight}px` }">
                        
                        <!-- Coverage Blocks -->
                        <div
                            v-for="cov in allVisualCoverage"
                            :key="'cov-' + cov.id"
                            :class="[
                              cov.is_panel ? 'bg-purple-100 border-purple-200' : 'bg-emerald-100 border-emerald-200',
                              { 'pointer-events-none opacity-50': draggedComp }
                            ]"
                            class="absolute border rounded-md group pointer-events-auto transition-opacity"
                            :style="getCoverageStyle(cov)"
                        >
                            <div class="flex justify-between items-start">
                                <div 
                                  :class="cov.is_panel ? 'text-purple-800' : 'text-emerald-800'"
                                  class="text-[10px] font-semibold px-1 pt-1 truncate"
                                >
                                  {{ cov.is_panel ? cov.panel_name : cov.adjudicator_name }}
                                </div>
                                <button
                                    @click.stop="deleteCoverage(cov)"
                                    :class="cov.is_panel ? 'text-purple-400 hover:text-red-500' : 'text-emerald-400 hover:text-red-500'"
                                    class="p-0.5 mr-0.5 mt-0.5 transition-colors"
                                    :title="cov.is_panel ? 'Remove Panel Coverage' : 'Remove Judge Coverage'"
                                >
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div 
                              :class="cov.is_panel ? 'text-purple-600' : 'text-emerald-600'"
                              class="text-[9px] px-1 truncate"
                            >
                              {{ cov.note }}
                            </div>
                        </div>

                        <!-- Competitions -->
                        <div
                            v-for="comp in allVisualCompetitions"
                            :key="comp.id"
                            class="absolute rounded-md shadow-sm border border-white/20 cursor-move text-xs text-white p-1 overflow-hidden hover:z-30 hover:shadow-lg transition-all group pointer-events-auto"
                            :class="[
                                getLevelColor(comp.level), 
                                { 
                                    'ring-2 ring-red-500': comp.has_conflicts,
                                    'pointer-events-none opacity-40 grayscale': draggedComp && draggedComp.id !== comp.id,
                                    'ring-4 ring-indigo-400 z-50 scale-105 shadow-2xl': draggedComp && draggedComp.id === comp.id
                                }
                            ]"
                            :style="getBlockStyle(comp)"
                            draggable="true"
                            @dragstart="onDragStart(comp, $event)"
                            @dragend="onDragEnd"
                            :title="`${comp.name} (${comp.estimated_duration_minutes}m)`"
                        >
                            <div class="flex justify-between items-start">
                                <div class="font-semibold truncate flex-1">
                                  {{ showCodes && comp.code ? comp.code : comp.name }}
                                </div>
                                <button 
                                    @click.stop="openCompetitionEditor(comp)"
                                    @mousedown.stop
                                    class="p-0.5 hover:bg-white/20 rounded opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 ml-1 z-30 relative"
                                    title="Edit"
                                >
                                    <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                    </svg>
                                </button>
                            </div>
                            <div class="flex items-center justify-between mt-0.5">
                                <span class="opacity-80">{{ new Date(comp.scheduled_time!).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
                                <div class="flex gap-0.5">
                                    <svg v-if="comp.adjudicator_id" class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                                    </svg>
                                </div>
                                <button
                                    @click.stop="unscheduleCompetition(comp)"
                                    @mousedown.stop
                                    class="text-white/70 hover:text-white hover:bg-red-500/50 rounded px-1 text-[10px] ml-1 transition-colors"
                                    title="Unschedule"
                                >
                                    ✕
                                </button>
                            </div>
                        </div>

                        <!-- Drop Preview -->
                        <div
                            v-if="dragOverStage && dragOverTime !== null"
                            class="absolute bg-indigo-500/30 border-2 border-dashed border-indigo-500 rounded-md z-50 pointer-events-none transition-all duration-75"
                            :style="getDropPreviewStyle"
                        >
                            <div class="absolute -top-8 left-1/2 -translate-x-1/2 bg-indigo-600 text-white text-[11px] font-bold px-2 py-1 rounded shadow-xl whitespace-nowrap z-50">
                                {{ dragTimeLabel }}
                                <!-- Arrow -->
                                <div class="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-indigo-600 rotate-45"></div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>

        </div>
      </div>
    </div>
  </div>

  <!-- Stage Modal -->
  <div v-if="showStageModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showStageModal = false">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div class="bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-4">
          <h3 class="text-lg font-bold text-white">{{ editingStage ? 'Edit Stage' : 'Create Stage' }}</h3>
        </div>
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Stage Name</label>
            <input v-model="stageForm.name" type="text" placeholder="e.g., Stage A" class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all outline-none" />
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Color</label>
            <div class="flex items-center gap-3">
              <input v-model="stageForm.color" type="color" class="w-12 h-12 rounded-lg cursor-pointer border-2 border-slate-200" />
              <div class="flex flex-wrap gap-2">
                <button v-for="color in stageColors" :key="color" @click="stageForm.color = color" class="w-8 h-8 rounded-lg border-2 transition-all" :class="stageForm.color === color ? 'border-slate-800 scale-110' : 'border-transparent'" :style="{ backgroundColor: color }"></button>
              </div>
            </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-slate-50 flex justify-end gap-3">
          <button @click="showStageModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors">Cancel</button>
          <button @click="saveStage" :disabled="!stageForm.name" class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50">Save</button>
        </div>
      </div>
  </div>

    <!-- Judge Coverage Modal (Updated for Multi-Select) -->
    <div
      v-if="showCoverageModal && coverageStage"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showCoverageModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4">
          <h3 class="text-lg font-bold text-white">Judge/Panel Assignment</h3>
          <p class="text-emerald-100 text-sm">Assign a single judge or panel to one or more stages</p>
        </div>
        
        <div class="p-6 space-y-4">
          <!-- Assignment Type Selector -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">Assignment Type</label>
            <div class="flex gap-3">
              <button
                @click="coverageForm.assignment_type = 'judge'"
                class="flex-1 px-4 py-3 rounded-xl border-2 transition-all font-medium"
                :class="coverageForm.assignment_type === 'judge'
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 text-slate-600 hover:border-slate-300'"
              >
                <div class="flex items-center justify-center gap-2">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  Single Judge
                </div>
              </button>
              <button
                @click="coverageForm.assignment_type = 'panel'"
                class="flex-1 px-4 py-3 rounded-xl border-2 transition-all font-medium"
                :class="coverageForm.assignment_type === 'panel'
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 text-slate-600 hover:border-slate-300'"
              >
                <div class="flex items-center justify-center gap-2">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  Judge Panel
                </div>
              </button>
            </div>
          </div>

          <!-- Single Judge Selection -->
          <div v-if="coverageForm.assignment_type === 'judge'">
            <label class="block text-sm font-semibold text-slate-700 mb-2">Select Judge</label>
            <select
              v-model="coverageForm.feis_adjudicator_id"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
            >
              <option value="">-- Select a judge --</option>
              <option 
                v-for="adj in adjudicators.filter(a => a.status === 'confirmed' || a.status === 'active')" 
                :key="adj.id" 
                :value="adj.id"
              >
                {{ adj.name }}
              </option>
            </select>
          </div>

          <!-- Panel Selection -->
          <div v-if="coverageForm.assignment_type === 'panel'">
            <label class="block text-sm font-semibold text-slate-700 mb-2">Select Panel</label>
            <select
              v-model="coverageForm.panel_id"
              class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 transition-all outline-none"
            >
              <option value="">-- Select a panel --</option>
              <option 
                v-for="panel in panels" 
                :key="panel.id" 
                :value="panel.id"
              >
                {{ panel.name }} ({{ panel.member_count }} judges)
              </option>
            </select>
            <p v-if="panels.length === 0" class="text-xs text-amber-600 mt-2">
              No panels created yet. Create panels in the Adjudicator Roster.
            </p>
          </div>
            
            <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-semibold text-slate-700 mb-2">Start Time</label>
                  <input v-model="coverageForm.start_time" type="time" class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 outline-none" />
                </div>
                <div>
                  <label class="block text-sm font-semibold text-slate-700 mb-2">End Time</label>
                  <input v-model="coverageForm.end_time" type="time" class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100 outline-none" />
                </div>
            </div>

            <!-- Multi-Stage Selection -->
            <div>
                <label class="block text-sm font-semibold text-slate-700 mb-2">Apply to Stages</label>
                <div class="max-h-40 overflow-y-auto border-2 border-slate-200 rounded-xl p-2 space-y-1">
                    <div v-for="stage in stages" :key="stage.id" class="flex items-center p-2 hover:bg-slate-50 rounded-lg">
                        <input 
                            type="checkbox" 
                            :id="`stage-${stage.id}`" 
                            :value="stage.id" 
                            v-model="coverageForm.selected_stage_ids"
                            class="w-5 h-5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                        >
                        <label :for="`stage-${stage.id}`" class="ml-3 text-sm font-medium text-slate-700 flex-1 cursor-pointer flex items-center gap-2">
                            <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: stage.color }"></span>
                            {{ stage.name }}
                        </label>
                    </div>
                </div>
                <p class="text-xs text-slate-500 mt-1">Select multiple stages to create a panel (Ping Pong judging)</p>
            </div>

            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Note</label>
              <input v-model="coverageForm.note" type="text" placeholder="e.g., Championship Panel A" class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-emerald-500 outline-none" />
            </div>
        </div>
        
        <div class="px-6 py-4 bg-slate-50 flex justify-end gap-3">
          <button @click="showCoverageModal = false" class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium">Close</button>
          <button 
            @click="addCoverage" 
            :disabled="(coverageForm.assignment_type === 'judge' && !coverageForm.feis_adjudicator_id) || (coverageForm.assignment_type === 'panel' && !coverageForm.panel_id) || coverageForm.selected_stage_ids.length === 0" 
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            Add Coverage
          </button>
        </div>
      </div>
    </div>

    <!-- Competition Editor Modal -->
    <CompetitionForm
      v-if="showCompetitionEditor && editingCompetition"
      :competition="editingCompetition"
      :feis-id="feisId"
      :is-creating="false"
      :stages="stages"
      :adjudicators="adjudicators"
      @save="saveCompetition"
      @cancel="closeCompetitionEditor"
    />

    <!-- Instant Scheduler Config Modal -->
    <div
      v-if="showInstantSchedulerConfigModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="showInstantSchedulerConfigModal = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 overflow-hidden max-h-[90vh] overflow-y-auto">
        <div class="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-4">
          <h3 class="text-lg font-bold text-white flex items-center gap-2">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Instant Scheduler
          </h3>
          <p class="text-amber-100 text-sm mt-1">Generate a complete schedule in one click</p>
  </div>
        
        <div class="p-6 space-y-5">
          <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
            <div class="flex items-start gap-2">
              <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p class="font-semibold">How it works:</p>
                <ul class="mt-1 space-y-1 text-amber-700">
                  <li>• Small competitions are merged (younger dancers compete up)</li>
                  <li>• Large competitions are split into groups</li>
                  <li>• Lunch breaks are automatically inserted</li>
                  <li>• The schedule is fully editable afterward</li>
                </ul>
              </div>
            </div>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Min Competition Size</label>
              <input
                v-model.number="instantSchedulerConfig.min_comp_size"
                type="number"
                min="2"
                max="20"
                class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-amber-500 focus:ring-4 focus:ring-amber-100 transition-all outline-none"
              />
              <p class="text-xs text-slate-500 mt-1">Competitions below this merge up</p>
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Max Competition Size</label>
              <input
                v-model.number="instantSchedulerConfig.max_comp_size"
                type="number"
                min="15"
                max="50"
                class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-amber-500 focus:ring-4 focus:ring-amber-100 transition-all outline-none"
              />
              <p class="text-xs text-slate-500 mt-1">Competitions above this are split</p>
            </div>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Feis Start Time</label>
              <input
                v-model="instantSchedulerConfig.feis_start_time"
                type="time"
                class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-amber-500 focus:ring-4 focus:ring-amber-100 transition-all outline-none"
              />
            </div>
            <div>
              <label class="block text-sm font-semibold text-slate-700 mb-2">Feis End Time</label>
              <input
                v-model="instantSchedulerConfig.feis_end_time"
                type="time"
                class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 focus:border-amber-500 focus:ring-4 focus:ring-amber-100 transition-all outline-none"
              />
            </div>
          </div>
          
          <div class="border-t border-slate-200 pt-4">
            <h4 class="font-semibold text-slate-700 mb-3">Lunch Break Settings</h4>
            <div class="grid grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-2">Window Start</label>
                <input
                  v-model="instantSchedulerConfig.lunch_window_start"
                  type="time"
                  class="w-full px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-amber-500 transition-all outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-2">Window End</label>
                <input
                  v-model="instantSchedulerConfig.lunch_window_end"
                  type="time"
                  class="w-full px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-amber-500 transition-all outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-2">Duration (min)</label>
                <input
                  v-model.number="instantSchedulerConfig.lunch_duration_minutes"
                  type="number"
                  min="15"
                  max="60"
                  class="w-full px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-amber-500 transition-all outline-none"
                />
              </div>
            </div>
          </div>
          
          <div class="border-t border-slate-200 pt-4">
            <h4 class="font-semibold text-slate-700 mb-3">Default Durations</h4>
            <p class="text-xs text-slate-500 mb-3">Used for competitions without entries yet</p>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-2">Grade Comps (min)</label>
                <input
                  v-model.number="instantSchedulerConfig.default_grade_duration_minutes"
                  type="number"
                  min="5"
                  max="45"
                  class="w-full px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-amber-500 transition-all outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-600 mb-2">Championship Comps (min)</label>
                <input
                  v-model.number="instantSchedulerConfig.default_champ_duration_minutes"
                  type="number"
                  min="10"
                  max="90"
                  class="w-full px-3 py-2 rounded-lg border-2 border-slate-200 focus:border-amber-500 transition-all outline-none"
                />
              </div>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <label class="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                v-model="instantSchedulerConfig.allow_two_year_merge_up" 
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-amber-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
            </label>
            <div>
              <span class="text-sm font-medium text-slate-700">Allow 2-year merge up</span>
              <p class="text-xs text-slate-500">If U8→U9 doesn't exist, try U8→U10</p>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <label class="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                v-model="instantSchedulerConfig.clear_existing" 
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-amber-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
            </label>
            <div>
              <span class="text-sm font-medium text-slate-700">Clear existing schedule</span>
              <p class="text-xs text-slate-500">Remove current schedule before generating new one</p>
            </div>
          </div>
        </div>
        
        <div class="px-6 py-4 bg-slate-50 flex justify-end gap-3">
          <button
            @click="showInstantSchedulerConfigModal = false"
            class="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            @click="runInstantScheduler"
            :disabled="instantSchedulerLoading"
            class="px-4 py-2 bg-amber-500 text-white rounded-lg font-bold hover:bg-amber-600 transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <template v-if="instantSchedulerLoading">
              <div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
              Generating...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate Schedule
            </template>
          </button>
        </div>
      </div>
    </div>

    <!-- Instant Scheduler Results Modal -->
    <div
      v-if="showInstantSchedulerModal && instantSchedulerResult"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="closeInstantSchedulerSummary"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden max-h-[90vh] overflow-y-auto">
        <div class="bg-gradient-to-r from-emerald-500 to-teal-500 px-6 py-4">
          <h3 class="text-lg font-bold text-white flex items-center gap-2">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Schedule Generated!
          </h3>
          <p class="text-emerald-100 text-sm mt-1">{{ instantSchedulerResult.message }}</p>
        </div>
        
        <div class="p-6 space-y-6">
          <!-- Summary Stats -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-emerald-50 rounded-xl p-4 text-center">
              <div class="text-3xl font-bold text-emerald-600">{{ instantSchedulerResult.total_competitions_scheduled }}</div>
              <div class="text-sm text-emerald-700">Scheduled</div>
            </div>
            <div class="bg-blue-50 rounded-xl p-4 text-center">
              <div class="text-3xl font-bold text-blue-600">{{ instantSchedulerResult.grade_competitions }}</div>
              <div class="text-sm text-blue-700">Grade Comps</div>
            </div>
            <div class="bg-purple-50 rounded-xl p-4 text-center">
              <div class="text-3xl font-bold text-purple-600">{{ instantSchedulerResult.championship_competitions }}</div>
              <div class="text-sm text-purple-700">Championships</div>
            </div>
            <div class="bg-amber-50 rounded-xl p-4 text-center">
              <div class="text-3xl font-bold text-amber-600">{{ instantSchedulerResult.lunch_holds.length }}</div>
              <div class="text-sm text-amber-700">Lunch Breaks</div>
            </div>
          </div>
          
          <!-- Merges Section -->
          <div v-if="instantSchedulerResult.merge_count > 0" class="border border-slate-200 rounded-xl overflow-hidden">
            <div class="bg-slate-50 px-4 py-3 flex items-center gap-2 border-b border-slate-200">
              <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              <span class="font-semibold text-slate-700">{{ instantSchedulerResult.merge_count }} Competition(s) Merged</span>
            </div>
            <div class="divide-y divide-slate-100 max-h-40 overflow-y-auto">
              <div 
                v-for="merge in instantSchedulerResult.normalized.merges" 
                :key="merge.source_competition_id"
                class="px-4 py-3 flex items-center gap-3 hover:bg-slate-50"
              >
                <span class="text-slate-600">{{ merge.source_competition_name }}</span>
                <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                <span class="text-slate-800 font-medium">{{ merge.target_competition_name }}</span>
                <span class="ml-auto text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                  {{ merge.dancers_moved }} dancer(s)
                </span>
              </div>
            </div>
          </div>
          
          <!-- Splits Section -->
          <div v-if="instantSchedulerResult.split_count > 0" class="border border-slate-200 rounded-xl overflow-hidden">
            <div class="bg-slate-50 px-4 py-3 flex items-center gap-2 border-b border-slate-200">
              <svg class="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span class="font-semibold text-slate-700">{{ instantSchedulerResult.split_count }} Competition(s) Split</span>
            </div>
            <div class="divide-y divide-slate-100 max-h-40 overflow-y-auto">
              <div 
                v-for="split in instantSchedulerResult.normalized.splits" 
                :key="split.original_competition_id"
                class="px-4 py-3 flex items-center gap-3 hover:bg-slate-50"
              >
                <span class="text-slate-800 font-medium">{{ split.competition_name }}</span>
                <span class="ml-auto text-xs">
                  <span class="bg-purple-100 text-purple-700 px-2 py-1 rounded-full">
                    Group A: {{ split.group_a_size }}
                  </span>
                  <span class="bg-purple-100 text-purple-700 px-2 py-1 rounded-full ml-1">
                    Group B: {{ split.group_b_size }}
                  </span>
                </span>
              </div>
            </div>
          </div>
          
          <!-- Warnings Section -->
          <div v-if="instantSchedulerResult.warnings.length > 0" class="border border-amber-200 rounded-xl overflow-hidden">
            <div class="bg-amber-50 px-4 py-3 flex items-center gap-2 border-b border-amber-200">
              <svg class="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span class="font-semibold text-amber-700">{{ instantSchedulerResult.warnings.length }} Warning(s)</span>
            </div>
            <div class="divide-y divide-amber-100 max-h-40 overflow-y-auto">
              <div 
                v-for="(warning, idx) in instantSchedulerResult.warnings" 
                :key="idx"
                class="px-4 py-3 text-sm"
                :class="warning.severity === 'critical' ? 'text-red-700 bg-red-50' : 'text-amber-700'"
              >
                <span :class="warning.severity === 'critical' ? 'font-semibold' : ''">
                  {{ warning.severity === 'critical' ? '🚫' : '⚠️' }}
                </span>
                {{ warning.message }}
              </div>
            </div>
          </div>
          
          <!-- Conflicts Section -->
          <div v-if="instantSchedulerResult.conflicts.length > 0" class="border border-red-200 rounded-xl overflow-hidden">
            <div class="bg-red-50 px-4 py-3 flex items-center gap-2 border-b border-red-200">
              <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="font-semibold text-red-700">{{ instantSchedulerResult.conflicts.length }} Conflict(s) Detected</span>
            </div>
            <div class="divide-y divide-red-100 max-h-40 overflow-y-auto">
              <div 
                v-for="(conflict, idx) in instantSchedulerResult.conflicts" 
                :key="idx"
                class="px-4 py-3 text-sm"
                :class="conflict.severity === 'error' ? 'text-red-700' : 'text-amber-700'"
              >
                {{ conflict.severity === 'error' ? '🚫' : '⚠️' }}
                {{ conflict.message }}
              </div>
            </div>
          </div>
          
          <p class="text-sm text-slate-500 text-center">
            You can now drag and drop competitions in the timeline to make adjustments.
          </p>
        </div>
        
        <div class="px-6 py-4 bg-slate-50 flex justify-end">
          <button
            @click="closeInstantSchedulerSummary"
            class="px-6 py-2 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700 transition-colors"
          >
            View Schedule
          </button>
        </div>
      </div>
    </div>

</template>

