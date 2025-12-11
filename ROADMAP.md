# OpenFeis Development Roadmap

> **Purpose:** This document guides future development of OpenFeis. Each phase is designed to be self-contained so it can be shared with an AI agent along with the README.md for context-aware implementation.

---

## Project Context

OpenFeis is an open-source Irish Dance competition management platform designed to replace fragile legacy systems like FeisWorx, QuickFeis, and the recently-failed GoFeis. The GoFeis failure at the Mid-America Oireachtas 2025—caused by dependency on cloud connectivity during critical tabulation—is the primary motivation for this project.

**Core Philosophy:** Local-first, offline-resilient, CLRG-compliant.

### Current State (v0.3.0)

| Component | Status | Notes |
|-----------|--------|-------|
| Scoring Engine | ✅ 85% | Irish Points, split ties, drop high/low, recall |
| Registration | ✅ 70% | Dancer profiles, eligibility filtering, pay-at-door |
| Judge Pad | ✅ 80% | Offline IndexedDB, sync on reconnect |
| Tabulator | ✅ 80% | Local mode, WebSocket updates |
| Admin | ✅ 75% | Feis/competition CRUD, syllabus generator |
| Scheduling | ✅ 85% | Visual Gantt, Instant Scheduler, conflict detection |
| Payments | ⚠️ 60% | Cart calculation, family max, Stripe stubbed |

---

## Phase 1: Local-First Resilience ⭐

**Priority:** CRITICAL  
**Goal:** Enable a full competition to run without internet connectivity.  
**Rationale:** This is THE differentiator. GoFeis failed because tabulation required the cloud.

### 1.1 Local Server Deployment Mode

**Description:** Create a deployment configuration that allows OpenFeis to run entirely on a local machine at a venue, with no external dependencies.

**Technical Requirements:**
- Create a `docker-compose.local.yml` for venue deployment
- SQLite database runs on local machine (already supported)
- FastAPI backend serves both API and static frontend
- No external API calls required for core functionality
- Document network setup (local WiFi router, tablet connections)

**Files to Modify/Create:**
- `docker-compose.local.yml` (new)
- `docs/venue-deployment.md` (new)
- `backend/main.py` (ensure static file serving works)

**Acceptance Criteria:**
- [ ] Can start OpenFeis on a laptop with `docker compose -f docker-compose.local.yml up`
- [ ] Judges on same WiFi can access Judge Pad and submit scores
- [ ] Tabulator shows results without any internet connectivity
- [ ] Works with airplane mode enabled on all devices

---

### 1.2 Offline Tabulator Component

**Description:** Build a version of the Tabulator Dashboard that can calculate and display results using only local data, without calling the cloud API.

**Technical Requirements:**
- Create a "Local Mode" toggle in the Tabulator UI
- In local mode, tabulator calculates Irish Points client-side using existing calculator logic
- Store competition results in IndexedDB alongside scores
- Display real-time results as judges submit scores on local network

**Files to Modify/Create:**
- `frontend/src/components/tabulator/LocalTabulatorDashboard.vue` (new)
- `frontend/src/services/localCalculator.ts` (new) - port Python calculator to TypeScript
- `frontend/src/stores/localResults.ts` (new)

**Implementation Notes:**
```typescript
// Port this logic from backend/scoring_engine/calculator.py
// The POINTS_TABLE and calculate_round logic should work identically
const POINTS_TABLE: Record<number, number> = {
  1: 100, 2: 75, 3: 65, 4: 60, 5: 56, 6: 53, 7: 50, 8: 47, 9: 45, 10: 43,
  // ... continue to 50: 1
};
```

**Acceptance Criteria:**
- [ ] Tabulator shows results without any API calls when in local mode
- [ ] Irish Points calculation matches server-side results exactly
- [ ] Recall calculation works correctly client-side
- [ ] Results update as judges submit scores on local network

---

### 1.3 Local Network Score Broadcasting

**Description:** Implement WebSocket or Server-Sent Events for real-time score updates on the local network.

**Technical Requirements:**
- Add WebSocket endpoint to FastAPI backend
- Broadcast score submissions to all connected clients
- Tabulator subscribes to score updates for live results
- Handle reconnection gracefully

**Files to Modify/Create:**
- `backend/api/websocket.py` (new)
- `backend/main.py` (mount WebSocket router)
- `frontend/src/services/scoreSocket.ts` (new)
- `frontend/src/stores/scoring.ts` (add WebSocket subscription)

**Implementation Notes:**
```python
# backend/api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def broadcast_score(self, score_data: dict):
        for connection in self.active_connections:
            await connection.send_json(score_data)
```

**Acceptance Criteria:**
- [ ] Tabulator receives score updates in <1 second on local network
- [ ] Multiple tabulators can view same competition simultaneously
- [ ] Connection drops and reconnects gracefully
- [ ] Works without internet (local network only)

---

### 1.4 Batch Cloud Sync

**Description:** When internet becomes available, sync all local data to the cloud for backup and public results.

**Technical Requirements:**
- Add "Sync to Cloud" button in admin panel
- Batch upload all unsynced scores, entries, and results
- Handle conflicts (cloud data vs local data)
- Show sync progress and status

**Files to Modify/Create:**
- `frontend/src/components/admin/CloudSync.vue` (new)
- `backend/api/routes.py` (add sync endpoints)
- `frontend/src/services/syncService.ts` (new)

**Acceptance Criteria:**
- [ ] Admin can manually trigger cloud sync
- [ ] All scores uploaded with correct timestamps
- [ ] Conflicts are flagged for manual resolution
- [ ] Public results page shows synced data

---

## Phase 2: Scheduling Engine ✅ COMPLETE

**Priority:** HIGH  
**Goal:** Replace manual scheduling with intelligent, conflict-aware automation.  
**Rationale:** The "10 PM finish" problem and parent frustration with overlapping competitions.

> **Status:** Phase 2 is complete. The scheduling engine includes:
> - ✅ Competition model with dance types, tempos, and duration estimation
> - ✅ Stage model and assignment
> - ✅ Visual Gantt drag-and-drop scheduler
> - ✅ Conflict detection (sibling, adjudicator, time overlap)
> - ✅ **Instant Scheduler** - One-click algorithmic schedule generation with merge/split normalization
> - ✅ Judge coverage blocks (time-based assignments)
> - ✅ Adjudicator roster management

### 2.1 Extend Competition Model

**Description:** Add fields required for scheduling and proper competition definition.

**Technical Requirements:**
- Add new fields to `Competition` model
- Create database migration
- Update API schemas
- Update syllabus generator to use new fields

**Database Changes:**
```python
# backend/scoring_engine/models_platform.py
class DanceType(str, Enum):
    REEL = "reel"
    LIGHT_JIG = "light_jig"
    SLIP_JIG = "slip_jig"
    TREBLE_JIG = "treble_jig"
    HORNPIPE = "hornpipe"
    TRADITIONAL_SET = "traditional_set"
    CONTEMPORARY_SET = "contemporary_set"
    TREBLE_REEL = "treble_reel"

class ScoringMethod(str, Enum):
    SOLO = "solo"  # 1 judge, raw scores
    CHAMPIONSHIP = "championship"  # 3-5 judges, Irish Points

class Competition(SQLModel, table=True):
    # ... existing fields ...
    
    # New fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None  # e.g., 113 for Reel
    bars: int = Field(default=48)  # Number of bars danced
    scoring_method: ScoringMethod = Field(default=ScoringMethod.SOLO)
    price_cents: int = Field(default=1000)  # $10.00 default
    max_entries: Optional[int] = None  # None = unlimited
    stage_id: Optional[UUID] = None  # FK to Stage (Phase 2.3)
    scheduled_time: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
```

**Files to Modify:**
- `backend/scoring_engine/models_platform.py`
- `backend/api/schemas.py`
- `backend/api/routes.py` (syllabus generation)
- `frontend/src/models/types.ts`
- `frontend/src/components/admin/SyllabusGenerator.vue`

**Acceptance Criteria:**
- [ ] Database migration runs successfully
- [ ] Syllabus generator creates competitions with dance_type and tempo
- [ ] Existing competitions still work (backward compatible)
- [ ] API returns new fields

---

### 2.2 Time Estimation Algorithm

**Description:** Calculate estimated duration for each competition based on entry count and dance parameters.

**Technical Requirements:**
- Implement duration estimation formula
- Account for setup time, rotation size, and dance length
- Update estimates as entries change

**Implementation Notes:**
```python
# backend/services/scheduling.py
def estimate_duration(
    entry_count: int,
    bars: int,
    dancers_per_rotation: int = 2,
    setup_time_minutes: int = 2,
    tempo_bpm: int = 113
) -> int:
    """
    Estimate competition duration in minutes.
    
    Formula: (entries / rotation) * (bars / tempo * 60) + setup
    
    Example: 50 dancers, 48 bars, 113bpm, 2 at a time
    - Rotations: 25
    - Time per rotation: 48/113 * 60 = ~25 seconds + transition
    - Total: ~15-20 minutes
    """
    rotations = math.ceil(entry_count / dancers_per_rotation)
    seconds_per_bar = 60 / tempo_bpm
    dance_time_seconds = bars * seconds_per_bar
    
    # Add 15 seconds between rotations for transitions
    total_seconds = rotations * (dance_time_seconds + 15)
    total_minutes = math.ceil(total_seconds / 60) + setup_time_minutes
    
    return total_minutes
```

**Files to Create/Modify:**
- `backend/services/scheduling.py` (new)
- `backend/api/routes.py` (add duration estimation endpoint)

**Acceptance Criteria:**
- [ ] Estimates within 20% of actual duration for typical competitions
- [ ] Recalculates when entry count changes
- [ ] Accounts for different dance types (championships take longer)

---

### 2.3 Stage Model and Assignment

**Description:** Create Stage entities and allow assigning competitions to stages.

**Technical Requirements:**
- Create `Stage` model linked to `Feis`
- Add stage assignment to competitions
- Create stage management UI

**Database Changes:**
```python
class Stage(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    name: str  # e.g., "Stage A", "Main Hall"
    color: Optional[str] = None  # For UI display, e.g., "#FF5733"
    
    feis: Feis = Relationship(back_populates="stages")
    competitions: List["Competition"] = Relationship(back_populates="stage")
```

**Files to Create/Modify:**
- `backend/scoring_engine/models_platform.py`
- `backend/api/schemas.py`
- `backend/api/routes.py`
- `frontend/src/components/admin/StageManager.vue` (new)

**Acceptance Criteria:**
- [ ] Can create/edit/delete stages for a feis
- [ ] Can assign competitions to stages
- [ ] UI shows stage color coding

---

### 2.4 Visual Gantt Scheduler

**Description:** Build a drag-and-drop scheduler for arranging competitions on stages over time.

**Technical Requirements:**
- Gantt-style horizontal timeline per stage
- Drag competitions to reorder or change stage
- Visual indication of duration
- Highlight conflicts (overlaps)

**Files to Create:**
- `frontend/src/components/admin/ScheduleGantt.vue` (replace placeholder)
- `frontend/src/components/admin/CompetitionBlock.vue`
- Use a Vue Gantt library or build custom with CSS Grid

**Implementation Notes:**
```vue
<!-- Gantt row for each stage -->
<div class="gantt-row" v-for="stage in stages" :key="stage.id">
  <div class="stage-label">{{ stage.name }}</div>
  <div class="timeline" @drop="handleDrop($event, stage.id)">
    <CompetitionBlock
      v-for="comp in getCompetitionsForStage(stage.id)"
      :key="comp.id"
      :competition="comp"
      :style="getBlockStyle(comp)"
      draggable="true"
      @dragstart="handleDragStart($event, comp)"
    />
  </div>
</div>
```

**Acceptance Criteria:**
- [x] Can drag competitions between stages
- [x] Can drag to reorder within a stage
- [x] Shows estimated duration visually
- [x] Saves changes to database

---

### 2.5 Instant Scheduler ✅ NEW

**Description:** One-click algorithmic schedule generation that normalizes competitions and places them optimally.

**Features Implemented:**
- **Competition Normalization:**
  - Merges small competitions (< min size) by moving younger dancers UP into older age groups
  - Never merges older dancers down (CLRG convention)
  - Splits large competitions (> max size) into Group A/B
  - Supports 1-year and 2-year merge up options
  
- **Stage Plan Construction:**
  - Respects judge coverage constraints
  - Identifies championship-capable stages (3+ judges)
  
- **Greedy Placement Algorithm:**
  - Sorts by level (lower first), then age (younger first)
  - Bin-packs competitions across stages
  - Balances load across stages
  
- **Lunch Break Insertion:**
  - Configurable lunch window (default 11:00-12:00)
  - Automatic 30-minute holds per stage

- **Configurable Options:**
  - Min/max competition sizes
  - Feis start/end times
  - Lunch window and duration
  - Default durations for planning

**Files Created:**
- `backend/services/instant_scheduler.py`
- `tests/test_instant_scheduler.py`
- Updated `backend/api/routes.py`, `schemas.py`
- Updated `frontend/src/components/admin/ScheduleGantt.vue`

**API Endpoint:**
- `POST /api/v1/feis/{feis_id}/schedule/instant`

---

### 2.6 Conflict Detection

**Description:** Automatically detect and flag scheduling conflicts.

**Conflict Types:**
1. **Sibling Conflict:** Same family has dancers on multiple stages at same time
2. **Adjudicator Conflict:** Judge assigned to competition containing their students
3. **Time Overlap:** Same dancer registered for overlapping competitions

**Technical Requirements:**
- Add `school_id` to Dancer model (link to teacher User)
- Add adjudicator assignment to Competition
- Build conflict detection service
- Display conflicts in scheduler UI

**Files to Create/Modify:**
- `backend/services/conflicts.py` (new)
- `backend/scoring_engine/models_platform.py` (add adjudicator assignment)
- `frontend/src/components/admin/ConflictWarnings.vue` (new)

**Implementation Notes:**
```python
# backend/services/conflicts.py
def detect_sibling_conflicts(feis_id: UUID, session: Session) -> List[Conflict]:
    """Find cases where siblings are scheduled on different stages at same time."""
    conflicts = []
    
    # Get all entries grouped by parent_id
    # Check for time overlaps across stages
    # Return list of conflicts with affected dancers/competitions
    
    return conflicts

def detect_adjudicator_conflicts(feis_id: UUID, session: Session) -> List[Conflict]:
    """Find cases where a judge is assigned to judge their own students."""
    # Compare adjudicator school_id against dancer school_ids in competition
    pass
```

**Acceptance Criteria:**
- [ ] Sibling conflicts highlighted in yellow
- [ ] Adjudicator conflicts highlighted in red (blocking)
- [ ] Can click conflict to see details
- [ ] Conflicts recalculate on schedule changes

---

## Phase 3: Financial Engine

**Priority:** HIGH  
**Goal:** Implement the complex pricing rules that families expect from feis registration.

### 3.1 Fee Structure Model

**Description:** Create a flexible pricing system that supports family caps, late fees, and fee categories.

**Database Changes:**
```python
class FeeCategory(str, Enum):
    QUALIFYING = "qualifying"  # Counts toward family max
    NON_QUALIFYING = "non_qualifying"  # Doesn't count (venue levy, merch)

class FeisSettings(SQLModel, table=True):
    """Per-feis configuration for pricing and registration."""
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", unique=True)
    
    family_max_cents: Optional[int] = Field(default=15000)  # $150.00
    late_fee_cents: int = Field(default=500)  # $5.00
    late_fee_date: Optional[date] = None
    change_fee_cents: int = Field(default=1000)  # $10.00
    registration_opens: Optional[datetime] = None
    registration_closes: Optional[datetime] = None

class FeeItem(SQLModel, table=True):
    """Additional fees beyond competition entry."""
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    name: str  # e.g., "Venue Levy", "Program Book"
    amount_cents: int
    category: FeeCategory = Field(default=FeeCategory.NON_QUALIFYING)
    required: bool = Field(default=False)  # Must be added to every order
```

**Files to Create/Modify:**
- `backend/scoring_engine/models_platform.py`
- `backend/api/schemas.py`
- `frontend/src/components/admin/FeisSettings.vue` (new)

**Acceptance Criteria:**
- [ ] Can configure family max per feis
- [ ] Can set late fee date and amount
- [ ] Can add venue levies and other fees

---

### 3.2 Cart Calculation with Family Maximum

**Description:** Implement the family max calculation in the shopping cart.

**Technical Requirements:**
- Sum all qualifying fees per family (same parent_id)
- Apply cap if total exceeds family_max_cents
- Show savings to user
- Handle multiple dancers from same family

**Files to Create/Modify:**
- `backend/services/cart.py` (new)
- `backend/api/routes.py` (cart calculation endpoint)
- `frontend/src/components/registration/CartSummary.vue` (update)

**Implementation Notes:**
```python
# backend/services/cart.py
def calculate_cart(
    parent_id: UUID,
    entries: List[Entry],
    feis_settings: FeisSettings,
    session: Session
) -> CartTotal:
    """
    Calculate cart total with family max applied.
    
    Returns:
        CartTotal with line items, subtotal, discount, and final total
    """
    qualifying_total = 0
    non_qualifying_total = 0
    
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if comp.fee_category == FeeCategory.QUALIFYING:
            qualifying_total += comp.price_cents
        else:
            non_qualifying_total += comp.price_cents
    
    # Apply family max to qualifying fees only
    if feis_settings.family_max_cents and qualifying_total > feis_settings.family_max_cents:
        discount = qualifying_total - feis_settings.family_max_cents
        qualifying_total = feis_settings.family_max_cents
    else:
        discount = 0
    
    return CartTotal(
        qualifying_subtotal=qualifying_total,
        non_qualifying_subtotal=non_qualifying_total,
        family_max_discount=discount,
        total=qualifying_total + non_qualifying_total
    )
```

**Acceptance Criteria:**
- [ ] Family max discount shows in cart
- [ ] Multiple dancers from same family share the cap
- [ ] Non-qualifying fees (venue levy) not affected by cap
- [ ] Cart updates in real-time as items added/removed

---

### 3.3 Late Fee Auto-Application

**Description:** Automatically add late fees after the specified date.

**Technical Requirements:**
- Check current date against feis late_fee_date
- Add late fee as non-qualifying line item
- Show notice to user that late fee applies

**Acceptance Criteria:**
- [ ] Late fee automatically added after deadline
- [ ] Late fee shown as separate line item
- [ ] Clear message explaining why late fee applies

---

### 3.4 Stripe Connect Integration

**Description:** Enable payment processing with Stripe Connect for multi-organizer payouts.

**Technical Requirements:**
- Stripe Connect onboarding flow for organizers
- Checkout session creation
- Webhook handling for payment confirmation
- Mark entries as paid on successful payment

**Files to Create/Modify:**
- `backend/services/stripe.py` (new)
- `backend/api/routes.py` (payment endpoints)
- `frontend/src/components/registration/StripeCheckout.vue` (new)
- Environment variables for Stripe keys

**Implementation Notes:**
```python
# backend/services/stripe.py
import stripe

async def create_checkout_session(
    feis: Feis,
    cart_total: CartTotal,
    entries: List[Entry],
    success_url: str,
    cancel_url: str
) -> str:
    """Create Stripe Checkout session and return URL."""
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[...],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        stripe_account=feis.stripe_account_id,  # Connect account
        metadata={
            "entry_ids": ",".join(str(e.id) for e in entries)
        }
    )
    
    return session.url
```

**Acceptance Criteria:**
- [ ] Organizers can connect Stripe account
- [ ] Parents can pay via Stripe Checkout
- [ ] Entries marked paid on successful payment
- [ ] Webhook handles payment confirmation

---

## Phase 4: Teacher Portal & Advancement

**Priority:** MEDIUM  
**Goal:** Enable school-level oversight and prevent "sandbagging" (dancing below earned level).

### 4.1 Placement History Model

**Description:** Track dancer placements to enable automatic advancement rules.

**Database Changes:**
```python
class PlacementHistory(SQLModel, table=True):
    """Records a dancer's placement in a competition."""
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id")
    competition_id: UUID = Field(foreign_key="competition.id")
    feis_id: UUID = Field(foreign_key="feis.id")
    rank: int
    irish_points: Optional[float] = None
    dance_type: DanceType
    level: CompetitionLevel
    date: date
    
    # For tracking advancement
    triggered_advancement: bool = Field(default=False)
```

**Files to Create/Modify:**
- `backend/scoring_engine/models_platform.py`
- `backend/api/routes.py` (auto-record placements when results finalized)

**Acceptance Criteria:**
- [ ] Placements recorded when competition results finalized
- [ ] Can query placement history by dancer
- [ ] History persists across feiseanna

---

### 4.2 Advancement Rules Engine

**Description:** Implement CLRG/NAFC advancement rules to automatically track level progression.

**Technical Requirements:**
- Define advancement rules per level/region
- Check placement history against rules
- Flag dancers who have "won out"
- Optional: Block registration at lower levels

**Implementation Notes:**
```python
# backend/services/advancement.py
ADVANCEMENT_RULES = {
    CompetitionLevel.BEGINNER: {
        "wins_required": 1,
        "next_level": CompetitionLevel.NOVICE,
        "per_dance": False  # Advances for all dances
    },
    CompetitionLevel.NOVICE: {
        "wins_required": 1,
        "next_level": CompetitionLevel.PRIZEWINNER,
        "per_dance": True  # Advances only for that specific dance
    },
    # ... etc
}

def check_advancement(dancer: Dancer, session: Session) -> List[AdvancementNotice]:
    """Check if dancer should advance based on placement history."""
    placements = session.exec(
        select(PlacementHistory)
        .where(PlacementHistory.dancer_id == dancer.id)
        .where(PlacementHistory.rank == 1)
    ).all()
    
    # Apply rules and return any pending advancements
```

**Acceptance Criteria:**
- [ ] System detects when dancer has won out
- [ ] Warning shown during registration for ineligible level
- [ ] Can override with admin approval

---

### 4.3 Teacher Dashboard

**Description:** Give teachers visibility into their school's registrations.

**Technical Requirements:**
- Link dancers to schools via `school_id` (references teacher User)
- Teacher can view all their students' registrations
- Teacher can flag entries as incorrect
- Bulk export for school records

**Files to Create:**
- `frontend/src/components/teacher/TeacherDashboard.vue` (new)
- `frontend/src/components/teacher/SchoolRoster.vue` (new)
- `backend/api/routes.py` (teacher-specific endpoints)

**Acceptance Criteria:**
- [ ] Teachers see roster of all their registered students
- [ ] Can filter by feis
- [ ] Can flag entries for organizer review
- [ ] Can export to CSV

---

### 4.4 Registration Flagging

**Description:** Allow teachers to flag incorrect entries for organizer review.

**Database Changes:**
```python
class EntryFlag(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    entry_id: UUID = Field(foreign_key="entry.id")
    flagged_by: UUID = Field(foreign_key="user.id")  # Teacher
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = Field(default=False)
    resolved_by: Optional[UUID] = None
    resolution_note: Optional[str] = None
```

**Acceptance Criteria:**
- [ ] Teachers can flag entry with reason
- [ ] Organizers see flagged entries in admin panel
- [ ] Can resolve flags with notes

---

## Phase 5: Check-In & Stage Management

**Priority:** MEDIUM  
**Goal:** Streamline day-of operations with digital check-in and stage displays.

### 5.1 Check-In Endpoint

**Description:** Create the API endpoint for QR code check-in scanning.

**Technical Requirements:**
- `POST /api/v1/checkin/{dancer_id}` endpoint
- Mark dancer as checked in for specific feis
- Return all their competition entries for that feis
- Update check-in status in real-time

**Database Changes:**
```python
class CheckIn(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id")
    feis_id: UUID = Field(foreign_key="feis.id")
    checked_in_at: datetime = Field(default_factory=datetime.utcnow)
    checked_in_by: Optional[UUID] = Field(foreign_key="user.id")  # Volunteer
```

**Files to Create/Modify:**
- `backend/api/routes.py`
- `frontend/src/components/checkin/CheckInScanner.vue` (new)

**Acceptance Criteria:**
- [ ] Scanning QR code marks dancer checked in
- [ ] Shows confirmation with dancer name and competitions
- [ ] Prevents double check-in (idempotent)

---

### 5.2 Stage Monitor Display

**Description:** Create a display for stage-side showing current and upcoming competitors.

**Technical Requirements:**
- Large, high-contrast display for visibility in dark venues
- Shows "Now Dancing" and "On Deck" (next up)
- Auto-advances based on check-in status
- Refreshes via WebSocket

**Files to Create:**
- `frontend/src/components/stage/StageMonitor.vue` (new)
- `frontend/src/components/stage/NowDancing.vue` (new)

**Implementation Notes:**
```vue
<!-- Large display optimized for projectors/TVs -->
<div class="stage-monitor">
  <div class="now-dancing">
    <h1>NOW DANCING</h1>
    <div class="competitor-number">#{{ currentCompetitor.number }}</div>
    <div class="dancer-name">{{ currentCompetitor.name }}</div>
  </div>
  
  <div class="on-deck">
    <h2>ON DECK</h2>
    <div v-for="next in nextUp" :key="next.id">
      #{{ next.number }} - {{ next.name }}
    </div>
  </div>
</div>
```

**Acceptance Criteria:**
- [ ] Display visible from 20+ feet away
- [ ] Updates automatically as competition progresses
- [ ] Shows competitor number and name
- [ ] Works offline (local network only)

---

### 5.3 Judge Tablet Check-In Integration

**Description:** Show check-in status on judge tablets so they know who's present.

**Technical Requirements:**
- Add check-in status to competitor list in JudgePad
- Visual indicator (green = checked in, gray = not yet)
- Filter to show only checked-in competitors

**Files to Modify:**
- `frontend/src/components/judge/JudgePad.vue`
- `backend/api/routes.py` (include check-in status in competitor response)

**Acceptance Criteria:**
- [ ] Judges see who has checked in
- [ ] Can optionally hide non-checked-in competitors
- [ ] Status updates in real-time

---

### 5.4 No-Show Management

**Description:** Handle competitors who don't show up for their competition.

**Technical Requirements:**
- Mark competitor as "No Show" after grace period
- No-shows receive 0 points (or lowest rank)
- Optionally remove from scoring grid
- Record no-show in system for reporting

**Acceptance Criteria:**
- [ ] Can mark competitor as no-show
- [ ] No-show recorded but doesn't break calculations
- [ ] Report of no-shows available to organizer

---

## Quick Wins (Can Implement Anytime)

These are small improvements that add value with minimal effort:

### QW-1: Predefined Comment Bank
Add quick-tap comments for judges instead of free-text only.

```typescript
const COMMENT_BANK = [
  "Timing", "Turnout", "Crossed feet", "Carriage", 
  "Extension", "Height", "Rhythm", "Stamina",
  "Beautiful!", "Well done"
];
```

### QW-2: Competition Entry Count Display
Show "3 of 20 spots filled" in eligibility picker.

### QW-3: Basic Audit Logging
Log score changes with timestamp and user ID.

### QW-4: Age Group Badges
Show competition age prominently in dancer profile.

### QW-5: PDF Results Export
Generate printable results sheets for posting.

---

## Technical Notes for Agents

### Project Structure
```
openfeis-server/
├── backend/
│   ├── api/
│   │   ├── auth.py      # JWT authentication
│   │   ├── routes.py    # All API endpoints
│   │   └── schemas.py   # Pydantic models
│   ├── db/
│   │   └── database.py  # SQLite connection
│   ├── scoring_engine/
│   │   ├── calculator.py     # Irish Points logic
│   │   ├── models.py         # Round, JudgeScore
│   │   └── models_platform.py # User, Feis, Competition, etc.
│   └── services/
│       ├── email.py
│       └── number_cards.py
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── admin/
│       │   ├── auth/
│       │   ├── judge/
│       │   ├── registration/
│       │   └── tabulator/
│       ├── services/
│       │   └── db.ts     # IndexedDB for offline
│       └── stores/
│           ├── auth.ts
│           └── scoring.ts
```

### Key Technical Decisions
- **Database:** SQLite with WAL mode (single file, portable)
- **ORM:** SQLModel (SQLAlchemy + Pydantic)
- **Auth:** JWT tokens with 24-hour expiry
- **Offline:** IndexedDB via `idb` library
- **Styling:** Tailwind CSS v4
- **State:** Pinia stores

### Running Locally
```bash
# Backend
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

### Creating Database Migrations
Since we're using SQLite and SQLModel, migrations are handled by recreating tables. For production, consider adding Alembic.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | Initial | Basic scoring, registration |
| 0.2.0 | - | Auth, email verification, number cards |
| 0.3.0 | Current | Local-first resilience, scheduling engine, Instant Scheduler |
| 0.4.0 | Phase 3 | Financial engine |
| 0.5.0 | Phase 4 | Teacher portal |
| 0.6.0 | Phase 5 | Check-in & stage management |
| 1.0.0 | TBD | Production ready |

