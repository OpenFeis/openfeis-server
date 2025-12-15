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

export type CompetitionLevel = 
  | 'first_feis'
  | 'beginner_1' 
  | 'beginner_2'
  | 'novice' 
  | 'prizewinner' 
  | 'preliminary_championship'
  | 'open_championship';

export type Gender = 'male' | 'female' | 'other';

// New scheduling types (uppercase to match backend enum values)
export type DanceType = 
  // Solo dances
  | 'REEL'
  | 'LIGHT_JIG'
  | 'SLIP_JIG'
  | 'SINGLE_JIG'
  | 'TREBLE_JIG'
  | 'HORNPIPE'
  | 'TRADITIONAL_SET'
  | 'CONTEMPORARY_SET'
  | 'TREBLE_REEL'
  // Figure/Ceili dances
  | 'TWO_HAND'
  | 'THREE_HAND'
  | 'FOUR_HAND'
  | 'SIX_HAND'
  | 'EIGHT_HAND';

export type ScoringMethod = 'SOLO' | 'CHAMPIONSHIP';

// Competition category for registration grouping (uppercase to match backend enum values)
export type CompetitionCategory = 'SOLO' | 'FIGURE' | 'CHAMPIONSHIP' | 'SPECIAL';

export interface User {
  id: string;
  email: string;
  role: RoleType;
  name: string;
  email_verified: boolean;
  is_feis_organizer: boolean;  // True if user can manage at least one feis (role or co-organizer)
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
  // Per-dance levels (optional - defaults to current_level if not set)
  level_reel?: CompetitionLevel;
  level_light_jig?: CompetitionLevel;
  level_slip_jig?: CompetitionLevel;
  level_single_jig?: CompetitionLevel;
  level_treble_jig?: CompetitionLevel;
  level_hornpipe?: CompetitionLevel;
  level_traditional_set?: CompetitionLevel;
  level_figure?: CompetitionLevel;
  is_adult?: boolean;
}

export interface Competition {
  id: string;
  feis_id: string;
  name: string;
  min_age: number;
  max_age: number;
  level: CompetitionLevel;
  gender?: Gender;
  code?: string; // Display code (e.g., "407SJ")
  // Competition category (solo, figure, championship)
  category?: CompetitionCategory;
  is_mixed?: boolean; // For figure dances - mixed gender team
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
  description?: string;
  allowed_levels?: CompetitionLevel[];
}

export interface StageJudgeCoverage {
  id: string;
  stage_id: string;
  stage_name: string;
  feis_adjudicator_id: string;
  adjudicator_name: string;
  feis_day: string; // ISO date
  start_time: string; // HH:MM
  end_time: string;   // HH:MM
  note?: string;
}

export interface Stage {
  id: string;
  feis_id: string;
  name: string;
  color?: string; // Hex color, e.g., "#FF5733"
  sequence: number;
  competition_count?: number;
  judge_coverage: StageJudgeCoverage[];
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
  adjudicator_id?: string;
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

// Dance type display info (keys match backend enum values)
export const DANCE_TYPE_INFO: Record<DanceType, { label: string; defaultTempo: number; icon: string }> = {
  // Solo dances
  REEL: { label: 'Reel', defaultTempo: 113, icon: '🎵' },
  LIGHT_JIG: { label: 'Light Jig', defaultTempo: 115, icon: '💫' },
  SLIP_JIG: { label: 'Slip Jig', defaultTempo: 113, icon: '✨' },
  SINGLE_JIG: { label: 'Single Jig', defaultTempo: 124, icon: '🪘' },
  TREBLE_JIG: { label: 'Treble Jig', defaultTempo: 73, icon: '🥁' },
  HORNPIPE: { label: 'Hornpipe', defaultTempo: 138, icon: '⚡' },
  TRADITIONAL_SET: { label: 'Traditional Set', defaultTempo: 113, icon: '🌟' },
  CONTEMPORARY_SET: { label: 'Contemporary Set', defaultTempo: 113, icon: '💎' },
  TREBLE_REEL: { label: 'Treble Reel', defaultTempo: 92, icon: '🔥' },
  // Figure/Ceili dances
  TWO_HAND: { label: '2-Hand', defaultTempo: 113, icon: '👯' },
  THREE_HAND: { label: '3-Hand', defaultTempo: 113, icon: '👯' },
  FOUR_HAND: { label: '4-Hand', defaultTempo: 115, icon: '👥' },
  SIX_HAND: { label: '6-Hand', defaultTempo: 113, icon: '👥' },
  EIGHT_HAND: { label: '8-Hand', defaultTempo: 115, icon: '🎭' },
};

// Solo dances shown in registration table
export const SOLO_DANCE_TYPES: DanceType[] = [
  'REEL', 'LIGHT_JIG', 'SLIP_JIG', 'SINGLE_JIG', 'TREBLE_JIG', 'HORNPIPE', 'TRADITIONAL_SET'
];

// Figure/Ceili dances shown in registration table
export const FIGURE_DANCE_TYPES: DanceType[] = [
  'TWO_HAND', 'THREE_HAND', 'FOUR_HAND', 'SIX_HAND', 'EIGHT_HAND'
];


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


// ============= Phase 4: Teacher Portal & Advancement Types =============

// --- Placement History ---

export interface PlacementHistory {
  id: string;
  dancer_id: string;
  dancer_name: string;
  competition_id: string;
  competition_name: string;
  feis_id: string;
  feis_name: string;
  rank: number;
  irish_points: number | null;
  dance_type: DanceType | null;
  level: CompetitionLevel;
  competition_date: string;  // ISO date
  triggered_advancement: boolean;
  created_at: string;  // ISO datetime
}

export interface DancerPlacementHistory {
  dancer_id: string;
  dancer_name: string;
  total_placements: number;
  first_place_count: number;
  placements: PlacementHistory[];
}

// --- Advancement ---

export interface AdvancementRule {
  level: CompetitionLevel;
  wins_required: number;
  next_level: CompetitionLevel;
  per_dance: boolean;
  description: string;
}

export interface AdvancementNotice {
  id: string;
  dancer_id: string;
  dancer_name: string;
  from_level: CompetitionLevel;
  to_level: CompetitionLevel;
  dance_type: DanceType | null;  // null = all dances
  acknowledged: boolean;
  acknowledged_at: string | null;
  overridden: boolean;
  override_reason: string | null;
  created_at: string;
}

export interface AdvancementCheck {
  dancer_id: string;
  dancer_name: string;
  current_level: CompetitionLevel;
  pending_advancements: AdvancementNotice[];
  eligible_levels: CompetitionLevel[];
  warnings: string[];
}

// --- Entry Flagging ---

export type FlagType = 'level_incorrect' | 'school_wrong' | 'other';

export interface EntryFlag {
  id: string;
  entry_id: string;
  dancer_name: string;
  competition_name: string;
  flagged_by: string;
  flagged_by_name: string;
  reason: string;
  flag_type: FlagType;
  resolved: boolean;
  resolved_by: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string;
}

export interface FlaggedEntries {
  feis_id: string;
  feis_name: string;
  total_flags: number;
  unresolved_count: number;
  flags: EntryFlag[];
}

export interface CreateFlagRequest {
  entry_id: string;
  reason: string;
  flag_type: FlagType;
}

export interface ResolveFlagRequest {
  flag_id: string;
  resolution_note: string;
}

// --- Teacher Dashboard ---

export interface TeacherStudentEntry {
  entry_id: string;
  dancer_id: string;
  dancer_name: string;
  competition_id: string;
  competition_name: string;
  level: CompetitionLevel;
  competitor_number: number | null;
  paid: boolean;
  feis_id: string;
  feis_name: string;
  feis_date: string;  // ISO date
  is_flagged: boolean;
  flag_id: string | null;
}

export interface SchoolStudent {
  id: string;
  name: string;
  dob: string;  // ISO date
  current_level: CompetitionLevel;
  gender: Gender;
  parent_name: string;
  entry_count: number;
  pending_advancements: number;
}

export interface SchoolRoster {
  school_id: string;
  teacher_name: string;
  total_students: number;
  students: SchoolStudent[];
}

export interface TeacherDashboard {
  teacher_id: string;
  teacher_name: string;
  total_students: number;
  total_entries: number;
  entries_by_feis: Record<string, number>;
  pending_advancements: number;
  recent_entries: TeacherStudentEntry[];
}

// --- Teacher Actions ---

export interface LinkDancerToSchoolRequest {
  dancer_id: string;
  school_id: string;
}

// Helper: Get level badge color
export function getLevelBadgeColor(level: CompetitionLevel): string {
  const colors: Record<CompetitionLevel, string> = {
    first_feis: 'bg-pink-100 text-pink-800',
    beginner_1: 'bg-green-100 text-green-800',
    beginner_2: 'bg-teal-100 text-teal-800',
    novice: 'bg-blue-100 text-blue-800',
    prizewinner: 'bg-purple-100 text-purple-800',
    preliminary_championship: 'bg-orange-100 text-orange-800',
    open_championship: 'bg-amber-100 text-amber-800',
  };
  return colors[level] || 'bg-gray-100 text-gray-800';
}

// Helper: Get human-readable level name
export function getLevelDisplayName(level: CompetitionLevel): string {
  const names: Record<CompetitionLevel, string> = {
    first_feis: 'First Feis',
    beginner_1: 'Beginner 1',
    beginner_2: 'Beginner 2',
    novice: 'Novice',
    prizewinner: 'Prizewinner',
    preliminary_championship: 'Prelim Champ',
    open_championship: 'Open Champ',
  };
  return names[level] || level;
}

// Helper: Get rank badge for placements
export function getRankBadge(rank: number): { color: string; icon: string } {
  if (rank === 1) return { color: 'bg-yellow-100 text-yellow-800', icon: '🥇' };
  if (rank === 2) return { color: 'bg-slate-200 text-slate-800', icon: '🥈' };
  if (rank === 3) return { color: 'bg-amber-100 text-amber-800', icon: '🥉' };
  return { color: 'bg-slate-100 text-slate-600', icon: '' };
}


// ============= Phase 5: Waitlist, Check-In, Refunds =============

export type CheckInStatus = 'not_checked_in' | 'checked_in' | 'scratched';
export type WaitlistStatus = 'waiting' | 'promoted' | 'expired' | 'cancelled';

// --- Waitlist ---

export interface WaitlistEntry {
  id: string;
  feis_id: string;
  feis_name: string;
  dancer_id: string;
  dancer_name: string;
  competition_id: string | null;
  competition_name: string | null;
  position: number;
  status: WaitlistStatus;
  offer_sent_at: string | null;
  offer_expires_at: string | null;
  created_at: string;
}

export interface WaitlistStatusResponse {
  feis_id: string;
  feis_name: string;
  total_waiting: number;
  competition_waitlists: Record<string, number>;
  global_waitlist_count: number;
  user_waitlist_entries: WaitlistEntry[];
}

export interface FeisCapacity {
  feis_id: string;
  feis_name: string;
  global_cap: number | null;
  current_dancer_count: number;
  spots_remaining: number | null;
  is_full: boolean;
  waitlist_enabled: boolean;
  waitlist_count: number;
}

export interface CompetitionCapacity {
  competition_id: string;
  competition_name: string;
  max_entries: number | null;
  current_entries: number;
  spots_remaining: number | null;
  is_full: boolean;
  waitlist_count: number;
}

// --- Check-In ---

export interface CheckInResult {
  entry_id: string;
  dancer_name: string;
  competitor_number: number | null;
  competition_name: string;
  status: CheckInStatus;
  checked_in_at: string | null;
  message: string;
}

export interface StageMonitorEntry {
  entry_id: string;
  competitor_number: number | null;
  dancer_name: string;
  school_name: string | null;
  check_in_status: CheckInStatus;
  is_current: boolean;
  is_on_deck: boolean;
}

export interface StageMonitorData {
  competition_id: string;
  competition_name: string;
  stage_name: string | null;
  feis_name: string;
  total_entries: number;
  checked_in_count: number;
  scratched_count: number;
  current_dancer: StageMonitorEntry | null;
  on_deck: StageMonitorEntry[];
  all_entries: StageMonitorEntry[];
}

export interface CheckInStats {
  competition_id: string;
  total_entries: number;
  checked_in: number;
  scratched: number;
  not_checked_in: number;
  check_in_percent: number;
}

export interface FeisCheckInSummary {
  feis_id: string;
  total_competitions: number;
  total_entries: number;
  total_checked_in: number;
  total_scratched: number;
  overall_check_in_percent: number;
  competitions: (CheckInStats & { competition_name: string })[];
}

// --- Refunds ---

export interface RefundPolicy {
  feis_id: string;
  feis_name: string;
  allow_scratches: boolean;
  scratch_refund_percent: number;
  scratch_deadline: string | null;
  can_scratch: boolean;
  refund_message: string;
}

export interface ScratchResult {
  entry_id: string;
  dancer_name: string;
  competition_name: string;
  refund_amount_cents: number;
  message: string;
}

export interface RefundLog {
  id: string;
  order_id: string;
  entry_id: string | null;
  amount_cents: number;
  reason: string;
  refund_type: 'full' | 'partial' | 'scratch';
  processed_by_name: string;
  created_at: string;
}

export interface OrderRefundSummary {
  order_id: string;
  original_total_cents: number;
  refund_total_cents: number;
  remaining_cents: number;
  status: PaymentStatus;
  refund_logs: RefundLog[];
}

// Helper: Get check-in status badge
export function getCheckInStatusBadge(status: CheckInStatus): { color: string; label: string } {
  const badges: Record<CheckInStatus, { color: string; label: string }> = {
    not_checked_in: { color: 'bg-slate-100 text-slate-600', label: 'Not Checked In' },
    checked_in: { color: 'bg-green-100 text-green-800', label: 'Checked In' },
    scratched: { color: 'bg-red-100 text-red-800', label: 'Scratched' },
  };
  return badges[status] || { color: 'bg-slate-100 text-slate-600', label: 'Unknown' };
}

// Helper: Get waitlist status badge
export function getWaitlistStatusBadge(status: WaitlistStatus): { color: string; label: string } {
  const badges: Record<WaitlistStatus, { color: string; label: string }> = {
    waiting: { color: 'bg-amber-100 text-amber-800', label: 'Waiting' },
    promoted: { color: 'bg-green-100 text-green-800', label: 'Promoted' },
    expired: { color: 'bg-red-100 text-red-800', label: 'Expired' },
    cancelled: { color: 'bg-slate-100 text-slate-600', label: 'Cancelled' },
  };
  return badges[status] || { color: 'bg-slate-100 text-slate-600', label: 'Unknown' };
}


// ============= Phase 6: Adjudicator Roster Management =============

export type AdjudicatorStatus = 'invited' | 'confirmed' | 'active' | 'declined';
export type AvailabilityType = 'available' | 'unavailable' | 'lunch';

// --- Adjudicator Roster ---

export interface FeisAdjudicator {
  id: string;
  feis_id: string;
  user_id: string | null;
  name: string;
  email: string | null;
  phone: string | null;
  credential: string | null;  // e.g., "TCRG", "ADCRG", "TMRF"
  organization: string | null;  // e.g., "CLRG", "NAFC", "CRN"
  school_affiliation_id: string | null;  // FK to User (teacher) for conflict detection
  school_affiliation_name: string | null;  // Display name
  status: AdjudicatorStatus;
  invite_sent_at: string | null;
  invite_expires_at: string | null;
  has_access_pin: boolean;
  created_at: string;
  confirmed_at: string | null;
}

export interface AdjudicatorListResponse {
  feis_id: string;
  feis_name: string;
  total_adjudicators: number;
  confirmed_count: number;
  invited_count: number;
  active_count: number;
  adjudicators: FeisAdjudicator[];
}

export interface AdjudicatorCreateRequest {
  name: string;
  email?: string;
  phone?: string;
  credential?: string;
  organization?: string;
  school_affiliation_id?: string;
  user_id?: string;
}

export interface AdjudicatorUpdateRequest {
  name?: string;
  email?: string;
  phone?: string;
  credential?: string;
  organization?: string;
  school_affiliation_id?: string;
  status?: AdjudicatorStatus;
  user_id?: string;
}

// --- Adjudicator Availability ---

export interface AvailabilityBlock {
  id: string;
  feis_adjudicator_id: string;
  feis_day: string;  // ISO date
  start_time: string;  // Time string, e.g., "08:00"
  end_time: string;  // Time string, e.g., "17:00"
  availability_type: AvailabilityType;
  note: string | null;
  created_at: string;
}

export interface AdjudicatorAvailabilityResponse {
  adjudicator_id: string;
  adjudicator_name: string;
  feis_id: string;
  feis_dates: string[];  // All dates of the feis
  availability_blocks: AvailabilityBlock[];
}

export interface AvailabilityBlockCreateRequest {
  feis_day: string;  // ISO date
  start_time: string;  // e.g., "08:00"
  end_time: string;  // e.g., "17:00"
  availability_type: AvailabilityType;
  note?: string;
}

export interface BulkAvailabilityCreateRequest {
  blocks: AvailabilityBlockCreateRequest[];
  replace_existing: boolean;
}

// --- Adjudicator Invites ---

export interface AdjudicatorInviteResponse {
  success: boolean;
  adjudicator_id: string;
  invite_link: string;
  expires_at: string;
  message: string;
}

export interface AdjudicatorAcceptInviteRequest {
  token: string;
}

export interface AdjudicatorAcceptInviteResponse {
  success: boolean;
  feis_id: string;
  feis_name: string;
  adjudicator_name: string;
  message: string;
  access_token: string | null;
  user: User | null;
}

// --- Day-of PIN Access ---

export interface GeneratePinResponse {
  success: boolean;
  adjudicator_id: string;
  adjudicator_name: string;
  pin: string;  // Only shown once!
  message: string;
}

export interface PinLoginRequest {
  feis_id: string;
  pin: string;
}

export interface PinLoginResponse {
  success: boolean;
  access_token: string;
  feis_id: string;
  feis_name: string;
  adjudicator_name: string;
  message: string;
}

// --- Capacity Metrics ---

export interface AdjudicatorCapacity {
  feis_id: string;
  feis_name: string;
  total_adjudicators: number;
  confirmed_count: number;
  active_count: number;
  grades_judges_per_stage: number;
  champs_judges_per_panel: number;
  max_grade_stages: number;
  max_champs_panels: number;
  recommendation: string;
}

// --- Scheduling Defaults ---

export interface SchedulingDefaults {
  feis_id: string;
  grades_judges_per_stage: number;
  champs_judges_per_panel: number;
  lunch_duration_minutes: number;
  lunch_window_start: string | null;  // Time string, e.g., "11:00"
  lunch_window_end: string | null;  // Time string, e.g., "13:00"
}

export interface SchedulingDefaultsUpdateRequest {
  grades_judges_per_stage?: number;
  champs_judges_per_panel?: number;
  lunch_duration_minutes?: number;
  lunch_window_start?: string;
  lunch_window_end?: string;
}

// Helper: Get adjudicator status badge
export function getAdjudicatorStatusBadge(status: AdjudicatorStatus): { color: string; label: string } {
  const badges: Record<AdjudicatorStatus, { color: string; label: string }> = {
    invited: { color: 'bg-amber-100 text-amber-800', label: 'Invited' },
    confirmed: { color: 'bg-green-100 text-green-800', label: 'Confirmed' },
    active: { color: 'bg-blue-100 text-blue-800', label: 'Active' },
    declined: { color: 'bg-red-100 text-red-800', label: 'Declined' },
  };
  return badges[status] || { color: 'bg-slate-100 text-slate-600', label: 'Unknown' };
}

// Helper: Get availability type badge
export function getAvailabilityTypeBadge(type: AvailabilityType): { color: string; label: string } {
  const badges: Record<AvailabilityType, { color: string; label: string }> = {
    available: { color: 'bg-green-100 text-green-800', label: 'Available' },
    unavailable: { color: 'bg-red-100 text-red-800', label: 'Unavailable' },
    lunch: { color: 'bg-amber-100 text-amber-800', label: 'Lunch' },
  };
  return badges[type] || { color: 'bg-slate-100 text-slate-600', label: 'Unknown' };
}

// Common credential types for autocomplete
export const ADJUDICATOR_CREDENTIALS = [
  { value: 'TCRG', label: 'TCRG (Teacher)' },
  { value: 'ADCRG', label: 'ADCRG (Adjudicator)' },
  { value: 'TMRF', label: 'TMRF (Teacher of Music)' },
  { value: 'SDCRG', label: 'SDCRG (Examiner)' },
];

// Common dance organizations for autocomplete
export const DANCE_ORGANIZATIONS = [
  { value: 'CLRG', label: 'CLRG - An Coimisiún' },
  { value: 'NAFC', label: 'NAFC - North American Feis Commission' },
  { value: 'CRN', label: 'CRN - An Comhdháil' },
  { value: 'WIDA', label: 'WIDA - World Irish Dance Association' },
];


// ============= Instant Scheduler Types =============

export interface InstantSchedulerRequest {
  min_comp_size?: number;
  max_comp_size?: number;
  lunch_window_start?: string;  // HH:MM format
  lunch_window_end?: string;  // HH:MM format
  lunch_duration_minutes?: number;
  allow_two_year_merge_up?: boolean;
  strict_no_exhibition?: boolean;
  feis_start_time?: string;  // HH:MM format
  feis_end_time?: string;  // HH:MM format
  clear_existing?: boolean;
  default_grade_duration_minutes?: number;  // Default duration for grades with no entries
  default_champ_duration_minutes?: number;  // Default duration for champs with no entries
}

export interface MergeAction {
  source_competition_id: string;
  target_competition_id: string;
  source_competition_name: string;
  target_competition_name: string;
  source_age_range: string;
  target_age_range: string;
  dancers_moved: number;
  reason: string;
  rationale: string;
}

export interface SplitAction {
  original_competition_id: string;
  new_competition_id: string;
  competition_name: string;
  original_size: number;
  group_a_size: number;
  group_b_size: number;
  reason: string;
  assignment_method: string;
}

export interface SchedulerWarning {
  code: string;
  message: string;
  competition_ids: string[];
  stage_ids: string[];
  severity: 'warning' | 'critical';
}

export interface NormalizationResult {
  merges: MergeAction[];
  splits: SplitAction[];
  warnings: SchedulerWarning[];
  final_competition_count: number;
}

export interface StagePlan {
  stage_id: string;
  stage_name: string;
  coverage_block_count: number;
  is_championship_capable: boolean;
  track: 'grades' | 'championships';
}

export interface PlacementResult {
  competition_id: string;
  competition_name: string;
  stage_id: string;
  stage_name: string;
  scheduled_start: string;
  scheduled_end: string;
  duration_minutes: number;
  entry_count: number;
}

export interface LunchHold {
  stage_id: string;
  stage_name: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

export interface InstantSchedulerResponse {
  success: boolean;
  message: string;
  normalized: NormalizationResult;
  stage_plan: StagePlan[];
  placements: PlacementResult[];
  lunch_holds: LunchHold[];
  warnings: SchedulerWarning[];
  conflicts: ScheduleConflict[];
  total_competitions_scheduled: number;
  total_competitions_unscheduled: number;
  merge_count: number;
  split_count: number;
  grade_competitions: number;
  championship_competitions: number;
}
