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
}

export interface Entry {
  id: string;
  dancer_id: string;
  competition_id: string;
  competitor_number?: number;
  paid: boolean;
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
