// ============= Scoring Types (Phase 1) =============

export interface JudgeScore {
  id: string;
  judge_id: string;
  competitor_id: string;
  round_id: string;
  value: number;
  timestamp: string;
  synced?: boolean; // Local-only flag
}

export interface Competitor {
  id: string;
  number: string;
  name: string;
  school?: string;
}

// ============= Platform Types (Phase 2) =============

export type RoleType = 'super_admin' | 'organizer' | 'teacher' | 'parent' | 'adjudicator';

export type CompetitionLevel = 'beginner' | 'novice' | 'prizewinner' | 'championship';

export type Gender = 'male' | 'female' | 'other';

// New scheduling types
export type DanceType = 
  | 'reel'
  | 'light_jig'
  | 'slip_jig'
  | 'treble_jig'
  | 'hornpipe'
  | 'traditional_set'
  | 'contemporary_set'
  | 'treble_reel';

export type ScoringMethod = 'solo' | 'championship';

export interface User {
  id: string;
  email: string;
  role: RoleType;
  name: string;
  email_verified: boolean;
}

export interface Feis {
  id: string;
  organizer_id: string;
  name: string;
  date: string; // ISO date
  location: string;
  stripe_account_id?: string;
}

export interface Dancer {
  id: string;
  parent_id: string;
  school_id?: string;
  name: string;
  dob: string; // ISO date (YYYY-MM-DD)
  current_level: CompetitionLevel;
  gender: Gender;
  clrg_number?: string;
}

export interface Competition {
  id: string;
  feis_id: string;
  name: string;
  min_age: number;
  max_age: number;
  level: CompetitionLevel;
  gender?: Gender;
  // New scheduling fields
  dance_type?: DanceType;
  tempo_bpm?: number;
  bars?: number;
  scoring_method?: ScoringMethod;
  price_cents?: number;
  max_entries?: number;
  stage_id?: string;
  scheduled_time?: string; // ISO datetime
  estimated_duration_minutes?: number;
  adjudicator_id?: string;
  entry_count?: number;
}

export interface Stage {
  id: string;
  feis_id: string;
  name: string;
  color?: string; // Hex color, e.g., "#FF5733"
  sequence: number;
  competition_count?: number;
}

export interface Entry {
  id: string;
  dancer_id: string;
  competition_id: string;
  competitor_number?: number;
  paid: boolean;
  pay_later: boolean;  // "Pay at Door" option
}

// ============= Registration Flow Types =============

export interface CartItem {
  competition: Competition;
  dancer: Dancer;
  fee: number;
}

export interface Cart {
  items: CartItem[];
  subtotal: number;
  familyCap: number;
  discount: number;
  total: number;
}

// ============= Syllabus Generation Types =============

export interface SyllabusGenerationRequest {
  feis_id: string;
  levels: CompetitionLevel[];
  min_age: number;
  max_age: number;
  genders: Gender[];
  dances: string[];
}

export interface SyllabusGenerationResponse {
  generated_count: number;
  message: string;
}

// ============= Judge Pad / Scoring Types =============

export interface CompetitionForScoring {
  id: string;
  name: string;
  feis_id: string;
  feis_name: string;
  level: CompetitionLevel;
  competitor_count: number;
}

export interface CompetitorForScoring {
  entry_id: string;
  competitor_number: number;
  dancer_name: string;
  dancer_school?: string;
  existing_score?: number;
  existing_notes?: string;
}

export interface ScoreSubmission {
  entry_id: string;
  competition_id: string;
  value: number;
  notes?: string;
}

export interface ScoreSubmissionResponse {
  id: string;
  entry_id: string;
  competition_id: string;
  value: number;
  notes?: string;
  timestamp: string;
}

// ============= Scheduling Types =============

export interface ScheduleConflict {
  conflict_type: 'sibling' | 'adjudicator' | 'time_overlap';
  severity: 'warning' | 'error';
  message: string;
  affected_competition_ids: string[];
  affected_dancer_ids: string[];
  affected_stage_ids: string[];
}

export interface ScheduledCompetition {
  id: string;
  name: string;
  stage_id?: string;
  stage_name?: string;
  scheduled_time?: string;
  estimated_duration_minutes: number;
  entry_count: number;
  level: CompetitionLevel;
  dance_type?: DanceType;
  has_conflicts: boolean;
}

export interface SchedulerViewResponse {
  feis_id: string;
  feis_name: string;
  feis_date: string;
  stages: Stage[];
  competitions: ScheduledCompetition[];
  conflicts: ScheduleConflict[];
}

export interface DurationEstimateRequest {
  entry_count: number;
  bars?: number;
  tempo_bpm?: number;
  dancers_per_rotation?: number;
  setup_time_minutes?: number;
}

export interface DurationEstimateResponse {
  estimated_minutes: number;
  rotations: number;
  breakdown: string;
}

// Dance type display info
export const DANCE_TYPE_INFO: Record<DanceType, { label: string; defaultTempo: number; icon: string }> = {
  reel: { label: 'Reel', defaultTempo: 113, icon: '🎵' },
  light_jig: { label: 'Light Jig', defaultTempo: 115, icon: '💫' },
  slip_jig: { label: 'Slip Jig', defaultTempo: 113, icon: '✨' },
  treble_jig: { label: 'Treble Jig', defaultTempo: 73, icon: '🥁' },
  hornpipe: { label: 'Hornpipe', defaultTempo: 138, icon: '⚡' },
  traditional_set: { label: 'Traditional Set', defaultTempo: 113, icon: '🌟' },
  contemporary_set: { label: 'Contemporary Set', defaultTempo: 113, icon: '💎' },
  treble_reel: { label: 'Treble Reel', defaultTempo: 92, icon: '🔥' },
};
