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


// ============= Financial Engine Types (Phase 3) =============

export type FeeCategory = 'qualifying' | 'non_qualifying';
export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'refunded' | 'pay_at_door';

export interface FeisSettings {
  id: string;
  feis_id: string;
  base_entry_fee_cents: number;
  per_competition_fee_cents: number;
  family_max_cents: number | null;
  late_fee_cents: number;
  late_fee_date: string | null;  // ISO date
  change_fee_cents: number;
  registration_opens: string | null;  // ISO datetime
  registration_closes: string | null;  // ISO datetime
  stripe_account_id: string | null;
  stripe_onboarding_complete: boolean;
}

export interface FeeItem {
  id: string;
  feis_id: string;
  name: string;
  description: string | null;
  amount_cents: number;
  category: FeeCategory;
  required: boolean;
  max_quantity: number;
  active: boolean;
}

export interface CartLineItem {
  id: string;
  type: 'competition' | 'base_fee' | 'fee_item';
  name: string;
  description: string | null;
  dancer_id: string | null;
  dancer_name: string | null;
  unit_price_cents: number;
  quantity: number;
  total_cents: number;
  category: FeeCategory;
}

export interface CartCalculationRequest {
  feis_id: string;
  items: Array<{ competition_id: string; dancer_id: string }>;
  fee_items?: Record<string, number>;  // {fee_item_id: quantity}
}

export interface CartCalculationResponse {
  line_items: CartLineItem[];
  qualifying_subtotal_cents: number;
  non_qualifying_subtotal_cents: number;
  subtotal_cents: number;
  family_discount_cents: number;
  family_cap_applied: boolean;
  family_cap_cents: number | null;
  late_fee_cents: number;
  late_fee_applied: boolean;
  late_fee_date: string | null;
  total_cents: number;
  dancer_count: number;
  competition_count: number;
  savings_percent: number;
}

export interface CheckoutRequest {
  feis_id: string;
  items: Array<{ competition_id: string; dancer_id: string }>;
  fee_items?: Record<string, number>;
  pay_at_door: boolean;
}

export interface CheckoutResponse {
  success: boolean;
  order_id: string | null;
  checkout_url: string | null;
  is_test_mode: boolean;
  message: string;
}

export interface Order {
  id: string;
  feis_id: string;
  user_id: string;
  subtotal_cents: number;
  qualifying_subtotal_cents: number;
  non_qualifying_subtotal_cents: number;
  family_discount_cents: number;
  late_fee_cents: number;
  total_cents: number;
  status: PaymentStatus;
  created_at: string;
  paid_at: string | null;
  entry_count: number;
}

export interface RegistrationStatus {
  is_open: boolean;
  message: string;
  opens_at: string | null;
  closes_at: string | null;
  is_late: boolean;
  late_fee_cents: number;
  stripe_enabled: boolean;
  payment_methods: ('stripe' | 'pay_at_door')[];
}

export interface StripeStatus {
  stripe_configured: boolean;
  stripe_mode: 'live' | 'test' | 'disabled';
  feis_connected: boolean;
  onboarding_complete: boolean;
  message: string;
}

// Helper function to format cents as currency
export function formatCents(cents: number, currency: 'USD' | 'EUR' | 'GBP' = 'USD'): string {
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£' };
  const symbol = symbols[currency] || '$';
  return `${symbol}${(cents / 100).toFixed(2)}`;
}
