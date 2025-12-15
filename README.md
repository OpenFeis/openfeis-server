# ☘️ Open Feis

**A modern, local-first Irish Dance competition management platform.**

Open Feis is an open-source alternative to legacy feis management systems. Built with resilience at its core, it guarantees data integrity and operational continuity—even during internet outages. No more "tabulation meltdowns."

[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](https://github.com/OpenFeis/openfeis-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/)

---

## 🎯 Vision

Replace fragile, expensive legacy systems with a **transparent, resilient, and user-friendly** platform that:

- **Works offline** — Judges can score without WiFi; data syncs automatically
- **Ensures accuracy** — CLRG-compliant Irish Points calculation with full audit trails
- **Reduces costs** — Runs on a $5/month server (or free tier)
- **Empowers organizers** — Auto-generate syllabi, manage registrations, handle payments

---

## ✨ Features

### For Everyone
- **Secure Authentication** — JWT-based login with bcrypt password hashing
- **Email Verification** — Verify your email address via Resend integration
- **Role-Based Access** — See only the features relevant to your role
- **Mobile-Friendly** — Responsive design with hamburger menu navigation on mobile devices
- **Demo Mode** — Explore the interface before creating an account

### For Parents & Guardians
- **Self-Service Registration** — Create your own account instantly
- **My Account Dashboard** — Manage your profile, change password, view registration history
- **Persistent Dancer Profiles** — Save dancer profiles once, reuse them across multiple feiseanna
- **Dancer Management** — Add, edit, and delete dancer profiles from your account
- **School Linking** — Link dancers to their teacher/school once, automatically visible to teachers
- **Smart Registration** — Select from saved dancers or create new ones when registering
- **Per-Dance Level Selection** — Set different competition levels for each dance type (e.g., Prizewinner in Reel, Novice in Hornpipe) 🆕
- **Dance-by-Dance Grid** — Visual registration table showing all available dances with level dropdowns 🆕
- **Figure/Ceili Dances** — Register for team dances (2-hand through 8-hand) by age group, with support for dancing up 🆕
- **Championship Registration** — Simple registration for Preliminary and Open Championships 🆕
- **Real-Time Eligibility** — See matched competitions instantly as you adjust levels 🆕
- **Flexible Payment** — Pay online via Stripe or choose "Pay at Door" for check-in payment
- **Family Maximum Cap** — Automatic savings when fees exceed the family cap (e.g., $150)
- **Late Fee Transparency** — Clear display of late fees when registering after the deadline
- **Server-Side Cart Calculation** — Accurate pricing with itemized breakdown
- **Registration History** — View all past registrations grouped by dancer

### For Judges (Adjudicators)
- **Offline Scoring** — Score dancers even when WiFi drops; syncs when connectivity returns
- **Clean Interface** — Large touch targets designed for iPad use at stage-side
- **Automatic Backup** — Scores saved locally to IndexedDB, then synced to server
- **Secure Access** — Only adjudicators can submit scores

### For Organizers
- **Feis Manager** — Create, edit, and manage feiseanna from the frontend (no SQL required)
- **Syllabus Generator** — Auto-generate 100+ competitions with one click (Age × Gender × Level × Dance)
- **Gender-Neutral by Default** — Creates open competitions (e.g., "U8 Reel") with optional Boys/Girls separation 🆕
- **Figure Dance Generation** — Generate team dance competitions (2-hand through 8-hand) by age only 🆕
- **Championship Generation** — Generate Preliminary and Open Championship events 🆕
- **Competition Categories** — Competitions organized into Solo, Figure, and Championship categories 🆕
- **Competition Manager** — View, filter, and manage all competitions in a feis
- **Competition Codes** — Auto-generated codes (e.g., "407SJ") with organizer override
- **Entry Manager** — Assign competitor numbers, mark payments, track registrations
- **Number Card Generator** — Create printable PDF number cards with QR codes for check-in
- **Cap Enforcement** — Set per-competition limits and global feis dancer caps
- **Waitlist Management** — Automatic waitlisting with configurable offer windows
- **Schedule Builder** — Visual drag-and-drop scheduler for arranging competitions on stages
- **Instant Scheduler** — One-click algorithmic schedule generation with automatic merge/split of competitions 🆕
- **Stage Management** — Create and manage multiple stages/areas for your feis
- **Adjudicator Roster** — Build a roster of judges before they have accounts, track invites and confirmations
- **Judge Coverage Blocks** — Assign judges to stages with specific time ranges (e.g., "Mary: Stage A, 9am-12pm")
- **Time Estimation** — Automatic duration estimates based on entry count and dance parameters
- **Conflict Detection** — Identify scheduling conflicts (sibling overlaps, adjudicator conflicts, judge double-booking)
- **Feis Settings** — Configure pricing, fees, registration windows, and payments per feis
- **Flexible Pricing** — Set base entry fee, per-competition fee, and family maximum cap
- **Late Fee Management** — Configure late fee amount and cutoff date
- **Fee Items** — Add custom fees like venue levy, program book, etc.
- **Order Tracking** — View all orders with payment status and itemized breakdowns
- **Refund Processing** — Process refunds with full audit logging 🆕
- **Stripe Connect Ready** — Payment infrastructure ready for online payments (stubbed)
- **Site Settings** — Configure email (Resend API key) and site-wide settings (Super Admin only)
- **Tabulator Dashboard** — Real-time results with Irish Points, Drop High/Low, and recall calculations
- **Protected Operations** — Only organizers can modify their own feiseanna
- **Multi-Organizer Support** — Add co-organizers to collaborate on feis planning 🆕
- **Granular Permissions** — Configure per-organizer access (edit feis, manage entries, manage schedule, etc.) 🆕

### For Volunteers (Check-In) 🆕
- **Stage-Centric Check-In** — Select a stage to see only its competitions
- **Auto-Select Current** — Dashboard auto-selects the competition closest to now
- **QR Code Scanning** — Scan competitor number cards for instant check-in
- **Manual Check-In** — Enter competitor number manually when QR unavailable
- **Bulk Operations** — Check in multiple dancers at once
- **Scratch Management** — Mark no-shows as scratched
- **Check-In Stats** — Real-time stats showing checked-in vs. total per competition

### For Stage Monitors 🆕
- **Full-Screen Display** — Large, readable display for sidestage viewing
- **Competition Codes** — Shows "NOW" and "NEXT" competition codes prominently
- **Stage Selection** — Filter to a specific stage
- **Keyboard Navigation** — Arrow keys to advance/go back
- **Stage Colors** — Each stage can have a distinct color theme

### For Tabulators & Public Results
- **Tabulator Dashboard** — Select feis and competition from dropdowns to view results
- **Live Results** — Real-time updates via WebSocket as judges submit scores
- **Irish Points Engine** — Automatic conversion from raw scores to CLRG Irish Points
- **Recall Calculator** — Auto-calculate top 50% for championships with tie extension
- **Tie-Breaking** — Proper "split points" algorithm for tied placements
- **Drop High/Low** — Support for 5-judge panels with automatic outlier removal
- **Detailed View** — Toggle per-judge scores, ranks, and points in the tabulator dashboard 🆕
- **Public Access** — Anyone can view results (no login required)
- **Local Mode** — Calculate results client-side when offline (toggle in UI)

### Local-First / Venue Mode
- **Offline Operation** — Run an entire feis without internet connectivity
- **Local Server Deployment** — Single Docker command starts everything on a laptop
- **WebSocket Broadcasting** — Scores propagate to all tabulators in under 1 second
- **Automatic Fallback** — If API is unreachable, Tabulator calculates results locally
- **Cloud Sync** — Batch upload all local scores to cloud server after the event
- **Conflict Resolution** — UI to resolve score conflicts when syncing
- **Network Resilience** — Graceful degradation during WiFi interruptions

### Teacher Portal & Advancement 🆕
- **Teacher Dashboard** — View all students linked to your school
- **School Roster** — Manage dancers, view levels, track entries
- **Placement History** — Full history of dancer placements across feiseanna
- **Advancement Rules Engine** — CLRG-compliant level progression tracking
- **Won Out Detection** — Automatic detection when dancers should advance
- **Per-Dance Advancement** — Support for per-dance (Novice/PW) vs all-dance (Beginner) advancement
- **Registration Flagging** — Teachers can flag incorrect entries for organizer review
- **Entry Export** — Export student entries to CSV or JSON
- **School Linking** — Link dancers to schools for teacher visibility

---

## 🏗️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.11, FastAPI | High performance, async, auto-generated OpenAPI docs |
| **Database** | SQLite (WAL mode) | Zero network latency, 10k+ reads/sec, single-file simplicity |
| **ORM** | SQLModel (SQLAlchemy) | Type-safe models with Pydantic validation |
| **Auth** | JWT + bcrypt (passlib, python-jose) | Stateless auth, secure password hashing |
| **Email** | Resend | Transactional emails (verification, notifications) |
| **Frontend** | Vue 3, TypeScript, Vite | Modern reactivity with Composition API |
| **Styling** | Tailwind CSS v4 | Utility-first, highly customizable |
| **State** | Pinia | Official Vue state management |
| **Offline** | IndexedDB (idb) | Local-first architecture for judge scoring |
| **Real-time** | WebSocket | Instant score broadcasting without polling |

### Architecture Philosophy: "The Monolith on a Stick"

We reject microservices complexity. Open Feis runs as a single deployable unit:
- One Python process
- One SQLite file  
- One static frontend build

This approach is easy to deploy, debug, and costs under $10/month.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **pnpm** or **npm**

### Installation

```bash
# Clone the repository
git clone https://github.com/OpenFeis/openfeis-server.git
cd openfeis-server

# Backend setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### Running Locally

**Terminal 1 — Backend:**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

**Access the app:**
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Admin Dashboard:** Use the **Admin** tab in the frontend (organizers/admins only)

> **Note:** The frontend dev server proxies `/api` requests to the backend automatically via `vite.config.ts`.

### Initial Data

On first run, the database is seeded with:
- A Super Admin user (`admin@openfeis.org`)
- A sample feis ("Great Irish Feis 2025")
- A sample competition

> **Local/Venue default (only when `OPENFEIS_LOCAL_MODE=true`):** Email: `admin@openfeis.org` Password: `admin123`  
> **Non-local deployments:** set `OPENFEIS_SEED_ADMIN_PASSWORD` (recommended) or check server logs for the generated initial password.

---

## 📁 Project Structure

```
openfeis-server/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   ├── auth.py             # Authentication utilities (JWT, password hashing)
│   │   ├── routes.py           # Router aggregation (imports all sub-routers)
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── websocket.py        # WebSocket connection manager
│   │   └── routers/            # Domain-specific API routes (16 files)
│   │       ├── auth.py         # Authentication endpoints
│   │       ├── users.py        # User management
│   │       ├── feis.py         # Feis CRUD, settings, Stripe
│   │       ├── feis_operations.py  # Scheduling, entries, check-in
│   │       ├── competitions.py # Competition CRUD
│   │       ├── entries.py      # Entry management
│   │       ├── adjudicators.py # Adjudicator roster & availability
│   │       ├── scoring.py      # Score submission & results
│   │       ├── scheduling.py   # Stage & schedule management
│   │       ├── checkin.py      # Check-in operations
│   │       ├── checkout.py     # Cart & payment processing
│   │       ├── waitlist.py     # Waitlist management
│   │       ├── advancement.py  # Level progression tracking
│   │       ├── teacher.py      # Teacher portal
│   │       ├── admin.py        # Admin operations
│   │       └── sync.py         # Offline sync
│   ├── db/
│   │   └── database.py         # SQLite connection & session
│   ├── services/
│   │   ├── email.py            # Email service (Resend integration)
│   │   ├── number_cards.py     # PDF generation for competitor numbers
│   │   ├── scheduling.py       # Time estimation & conflict detection
│   │   ├── instant_scheduler.py # Algorithmic schedule generation
│   │   ├── cart.py             # Cart calculation with family cap logic
│   │   ├── stripe.py           # Stripe Connect integration (stubbed)
│   │   ├── waitlist.py         # Waitlist management
│   │   ├── checkin.py          # Check-in operations
│   │   └── refund.py           # Refund processing
│   ├── utils/
│   │   └── competition_codes.py  # Competition code generation
│   └── scoring_engine/
│       ├── calculator.py       # Irish Points calculation logic
│       ├── models.py           # Round, JudgeScore models
│       └── models_platform.py  # User, Feis, Dancer, etc.
├── frontend/
│   ├── src/
│   │   ├── App.vue             # Main application component
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   │   ├── FeisManager.vue         # Feis CRUD operations
│   │   │   │   ├── CompetitionManager.vue  # Competition listing/management
│   │   │   │   ├── EntryManager.vue        # Entry/registration management
│   │   │   │   ├── SyllabusGenerator.vue   # Matrix-based competition generator
│   │   │   │   ├── ScheduleGantt.vue       # Visual drag-and-drop scheduler with coverage
│   │   │   │   ├── AdjudicatorManager.vue  # Judge roster management 🆕
│   │   │   │   ├── FeisSettingsManager.vue # Pricing, fees & registration config
│   │   │   │   ├── SiteSettings.vue        # Email & site configuration
│   │   │   │   └── CloudSync.vue           # Offline-to-cloud sync UI
│   │   │   ├── account/
│   │   │   │   └── AccountPage.vue         # User account management (profile, dancers, history)
│   │   │   ├── auth/
│   │   │   │   ├── AuthModal.vue           # Login/Register modal wrapper
│   │   │   │   ├── LoginForm.vue           # Login form component
│   │   │   │   ├── RegisterForm.vue        # Registration form component
│   │   │   │   ├── EmailVerification.vue   # Email verification page
│   │   │   │   └── EmailVerificationBanner.vue  # Unverified email warning
│   │   │   ├── judge/
│   │   │   │   └── JudgePad.vue
│   │   │   ├── registration/
│   │   │   │   ├── DancerProfileForm.vue
│   │   │   │   ├── DanceRegistrationTable.vue  # Per-dance level grid 🆕
│   │   │   │   ├── EligibilityPicker.vue
│   │   │   │   └── CartSummary.vue
│   │   │   ├── checkin/                      # 🆕
│   │   │   │   ├── CheckInDashboard.vue      # Stage-centric check-in UI
│   │   │   │   └── StageMonitor.vue          # Full-screen stage display
│   │   │   └── tabulator/
│   │   │       └── TabulatorDashboard.vue
│   │   ├── models/
│   │   │   └── types.ts        # TypeScript interfaces
│   │   ├── services/
│   │   │   ├── db.ts           # IndexedDB for offline storage
│   │   │   ├── localCalculator.ts  # Client-side Irish Points calculator
│   │   │   ├── scoreSocket.ts  # WebSocket client for real-time updates
│   │   │   └── syncService.ts  # Cloud sync service
│   │   └── stores/
│   │       ├── auth.ts         # Pinia store for authentication
│   │       ├── scoring.ts      # Pinia store for scores
│   │       └── localResults.ts # Pinia store for offline results
│   └── package.json
├── tests/
│   └── test_recall.py          # Unit tests
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Production container orchestration
├── docker-compose.local.yml    # Venue/offline deployment config
├── Caddyfile                   # Reverse proxy + HTTPS config
├── docs/
│   └── venue-deployment.md     # Offline deployment guide
├── deploy.sh                   # Deployment helper script
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🔌 API Reference

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/auth/register` | Create new account (default role: parent) | No |
| `POST` | `/api/v1/auth/login` | Login and receive JWT token | No |
| `GET` | `/api/v1/auth/me` | Get current user info | Yes |
| `PUT` | `/api/v1/auth/profile` | Update current user's name | Yes |
| `PUT` | `/api/v1/auth/password` | Change password (requires current password) | Yes |
| `POST` | `/api/v1/auth/verify-email` | Verify email with token from email link | No |
| `POST` | `/api/v1/auth/resend-verification` | Resend verification email (rate limited) | No |
| `GET` | `/api/v1/auth/email-status` | Check verification status | Yes |

### Scoring Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/scores` | Submit a single judge score | Adjudicator |
| `POST` | `/api/v1/scores/batch` | Submit multiple scores (for sync) | Adjudicator |
| `GET` | `/api/v1/rounds` | List all rounds | No |
| `GET` | `/api/v1/results/{round_id}` | Get calculated results for a round | No |

### Tabulator / Results Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/tabulator/competitions` | List competitions with scores (for dropdown) | No |
| `GET` | `/api/v1/competitions/{id}/results` | Get full results with dancer names, recall status | No |

### Feis Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/feis` | Create a new feis | Organizer/Admin |
| `GET` | `/api/v1/feis` | List all feiseanna | No |
| `GET` | `/api/v1/feis/mine` | List feiseanna current user can manage 🆕 | Organizer/Admin |
| `GET` | `/api/v1/feis/{id}` | Get a single feis | No |
| `PUT` | `/api/v1/feis/{id}` | Update a feis | Owner/Co-organizer/Admin |
| `DELETE` | `/api/v1/feis/{id}` | Delete a feis | Owner/Admin (not co-organizers) |

### Co-Organizer Management 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{feis_id}/organizers` | List all organizers for a feis | Organizer of feis |
| `POST` | `/api/v1/feis/{feis_id}/organizers` | Add a co-organizer to a feis | Organizer with `can_add_organizers` |
| `PUT` | `/api/v1/feis/{feis_id}/organizers/{id}` | Update co-organizer permissions | Organizer with `can_add_organizers` |
| `DELETE` | `/api/v1/feis/{feis_id}/organizers/{id}` | Remove a co-organizer | Organizer with `can_add_organizers` |

### Competition Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/competitions` | Create competition for a feis |
| `GET` | `/api/v1/feis/{feis_id}/competitions` | List competitions in a feis |
| `GET` | `/api/v1/competitions/{id}` | Get a single competition |
| `PUT` | `/api/v1/competitions/{id}` | Update a competition |
| `DELETE` | `/api/v1/competitions/{id}` | Delete a competition |

### Entry Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/entries` | Create an entry (with pay_later option) | Yes |
| `POST` | `/api/v1/entries/batch` | Create multiple entries (checkout) | Yes |
| `GET` | `/api/v1/entries` | List all entries | No |
| `PUT` | `/api/v1/entries/{id}` | Update an entry (set number, mark paid) | No |
| `DELETE` | `/api/v1/entries/{id}` | Delete an entry | Yes |
| `DELETE` | `/api/v1/feis/{id}/competitions/empty` | Delete all empty competitions | Organizer/Admin |

### Dancer Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/dancers` | Create a dancer profile | Yes |
| `GET` | `/api/v1/dancers` | List all dancers | No |
| `GET` | `/api/v1/dancers/mine` | List current user's dancers | Yes |
| `PUT` | `/api/v1/dancers/{id}` | Update a dancer profile | Yes (owner) |
| `DELETE` | `/api/v1/dancers/{id}` | Delete a dancer (if no entries) | Yes (owner) |
| `GET` | `/api/v1/me/entries` | Get all entries for current user's dancers | Yes |

### Admin Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/admin/syllabus/generate` | Auto-generate competitions | Organizer/Admin |
| `PUT` | `/api/v1/users/{id}` | Update a user's name/role | Super Admin |
| `GET` | `/api/v1/users` | List all users | No |
| `GET` | `/api/v1/admin/settings` | Get site settings (email config, etc.) | Super Admin |
| `PUT` | `/api/v1/admin/settings` | Update site settings | Super Admin |

### Number Card PDF Generation

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{feis_id}/number-cards` | Bulk PDF of all number cards (sorted by school, name) | Organizer/Admin |
| `GET` | `/api/v1/entries/{entry_id}/number-card` | Single card reprint | Organizer/Admin |

### Stage Management 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/feis/{feis_id}/stages` | Create a new stage | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/stages` | List stages for a feis | No |
| `PUT` | `/api/v1/stages/{stage_id}` | Update a stage | Organizer/Admin |
| `DELETE` | `/api/v1/stages/{stage_id}` | Delete a stage | Organizer/Admin |

### Scheduling

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{feis_id}/scheduler` | Get all scheduler data (stages, competitions, conflicts) | No |
| `PUT` | `/api/v1/competitions/{id}/schedule` | Update competition schedule (stage, time, duration) | Organizer/Admin |
| `POST` | `/api/v1/feis/{feis_id}/schedule/batch` | Batch update multiple competition schedules | Organizer/Admin |
| `POST` | `/api/v1/feis/{feis_id}/schedule/instant` | Generate instant schedule with merge/split normalization 🆕 | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/scheduling-conflicts` | Detect and return scheduling conflicts | Organizer/Admin |

### Adjudicator Roster 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{feis_id}/adjudicators` | List adjudicators on a feis roster | No |
| `POST` | `/api/v1/feis/{feis_id}/adjudicators` | Add adjudicator to roster (can link existing user or create placeholder) | Organizer/Admin |
| `PUT` | `/api/v1/feis/{feis_id}/adjudicators/{id}` | Update adjudicator info | Organizer/Admin |
| `DELETE` | `/api/v1/feis/{feis_id}/adjudicators/{id}` | Remove adjudicator from roster | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/adjudicator-capacity` | Get judge capacity metrics (how many stages/panels can run) | Organizer/Admin |
| `POST` | `/api/v1/adjudicators/{id}/invite` | Send email invite to adjudicator | Organizer/Admin |
| `POST` | `/api/v1/adjudicators/{id}/generate-pin` | Generate day-of access PIN | Organizer/Admin |

### Stage Judge Coverage 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/stages/{stage_id}/coverage` | List judge coverage blocks for a stage | No |
| `POST` | `/api/v1/stages/{stage_id}/coverage` | Add a coverage block (judge + date + time range) | Organizer/Admin |
| `DELETE` | `/api/v1/stage-coverage/{coverage_id}` | Remove a coverage block | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/judge-schedule` | Get all coverage blocks across all stages (cross-stage view) | No |

### Financial Engine

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{feis_id}/settings` | Get feis pricing/registration settings | No |
| `PUT` | `/api/v1/feis/{feis_id}/settings` | Update feis settings | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/fee-items` | List additional fee items | No |
| `POST` | `/api/v1/feis/{feis_id}/fee-items` | Create a fee item (venue levy, etc.) | Organizer/Admin |
| `PUT` | `/api/v1/fee-items/{id}` | Update a fee item | Organizer/Admin |
| `DELETE` | `/api/v1/fee-items/{id}` | Delete a fee item | Organizer/Admin |
| `GET` | `/api/v1/feis/{feis_id}/registration-status` | Check if registration is open, payment methods | No |
| `POST` | `/api/v1/cart/calculate` | Calculate cart with family cap & late fees | Yes |
| `POST` | `/api/v1/checkout` | Complete checkout (pay now or pay later) | Yes |
| `GET` | `/api/v1/checkout/success` | Handle successful payment redirect | No |
| `GET` | `/api/v1/orders` | List orders for current user | Yes |
| `GET` | `/api/v1/orders/{id}` | Get order details | Yes |
| `GET` | `/api/v1/feis/{feis_id}/stripe-status` | Check Stripe connection status | No |
| `POST` | `/api/v1/feis/{feis_id}/stripe-onboarding` | Start Stripe Connect onboarding | Organizer/Admin |

### Teacher Portal 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/teacher/dashboard` | Get teacher dashboard with overview | Teacher |
| `GET` | `/api/v1/teacher/roster` | Get school roster (all linked students) | Teacher |
| `GET` | `/api/v1/teacher/entries` | Get all entries for school students | Teacher |
| `GET` | `/api/v1/teacher/export` | Export entries to CSV/JSON | Teacher |
| `POST` | `/api/v1/dancers/{id}/link-school` | Link dancer to school | Yes |
| `DELETE` | `/api/v1/dancers/{id}/unlink-school` | Unlink dancer from school | Yes |

### Placement & Advancement 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/advancement/rules` | Get all advancement rules | No |
| `GET` | `/api/v1/dancers/{id}/placements` | Get dancer's placement history | No |
| `POST` | `/api/v1/placements` | Record a placement | Organizer/Admin |
| `GET` | `/api/v1/dancers/{id}/advancement` | Check dancer's advancement status | No |
| `POST` | `/api/v1/advancement/{id}/acknowledge` | Acknowledge advancement notice | Yes |
| `POST` | `/api/v1/advancement/{id}/override` | Override advancement (admin) | Organizer/Admin |

### Entry Flagging

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/entries/{id}/flag` | Flag an entry for review | Teacher |
| `GET` | `/api/v1/feis/{id}/flags` | Get all flagged entries for feis | Organizer/Admin |
| `POST` | `/api/v1/flags/{id}/resolve` | Resolve a flagged entry | Organizer/Admin |

### Waitlist & Capacity 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/feis/{id}/capacity` | Get feis capacity info (total, used, available) | No |
| `GET` | `/api/v1/competitions/{id}/capacity` | Get competition capacity info | No |
| `POST` | `/api/v1/waitlist/add` | Add dancer to waitlist | Yes |
| `GET` | `/api/v1/waitlist/mine` | Get current user's waitlist entries | Yes |
| `POST` | `/api/v1/waitlist/{id}/accept` | Accept a waitlist spot offer | Yes |
| `POST` | `/api/v1/waitlist/{id}/cancel` | Cancel waitlist entry | Yes |
| `GET` | `/api/v1/feis/{id}/waitlist` | View full waitlist (organizers only) | Organizer/Admin |

### Check-In System 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/checkin` | Check in an entry by ID | Organizer/Admin |
| `POST` | `/api/v1/checkin/by-number` | Check in by competitor number | Organizer/Admin |
| `POST` | `/api/v1/checkin/bulk` | Bulk check-in multiple entries | Organizer/Admin |
| `POST` | `/api/v1/checkin/{id}/undo` | Undo a check-in | Organizer/Admin |
| `GET` | `/api/v1/checkin/qr/{dancer_id}` | Look up entry by QR code data | No |
| `GET` | `/api/v1/competitions/{id}/stage-monitor` | Get stage monitor data | No |
| `GET` | `/api/v1/competitions/{id}/checkin-stats` | Get check-in statistics | No |
| `GET` | `/api/v1/feis/{id}/checkin-summary` | Get feis-wide check-in summary | No |

### Refunds 🆕

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/orders/{id}/refund` | Process a refund | Organizer/Admin |

### Example: Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@openfeis.org",
    "password": "YOUR_PASSWORD"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "admin@openfeis.org",
    "name": "System Administrator",
    "role": "super_admin"
  }
}
```

### Example: Generate Syllabus (Authenticated)

```bash
curl -X POST http://localhost:8000/api/v1/admin/syllabus/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "feis_id": "your-feis-uuid",
    "levels": ["beginner_1", "novice", "prizewinner"],
    "min_age": 5,
    "max_age": 16,
    "genders": ["male", "female"],
    "dances": ["Reel", "Light Jig", "Slip Jig"]
  }'
```

**Response:**
```json
{
  "generated_count": 126,
  "message": "Successfully created 126 competitions for Great Irish Feis 2025."
}
```

> **Competition Levels:** `first_feis`, `beginner_1`, `beginner_2`, `novice`, `prizewinner`, `preliminary_championship`, `open_championship`

---

## 🔐 Authentication

Open Feis uses JWT (JSON Web Token) authentication with bcrypt password hashing.

### User Roles

| Role | Permissions |
|------|-------------|
| `super_admin` | Full access to everything (admin, judging, all features) |
| `organizer` | Create/manage feiseanna, generate syllabus, manage entries |
| `adjudicator` | Access Judge Pad, submit scores |
| `teacher` | View results, manage school dancers (coming soon) |
| `parent` | Register dancers, view results |

### How It Works

1. **Registration** — New users register with email/password (default role: `parent`)
2. **Login** — Users receive a JWT token valid for 24 hours
3. **Protected Routes** — Backend validates token and checks role permissions
4. **Frontend UI** — Navigation and features adapt based on user role

### Security Features

- **Password Hashing** — bcrypt with automatic salting
- **JWT Tokens** — Stateless authentication, no server-side sessions
- **Role Enforcement** — Backend rejects unauthorized requests regardless of frontend
- **Demo Mode** — Unauthenticated users can explore UI but cannot submit data

---

## 📧 Email Setup (Resend)

Open Feis uses [Resend](https://resend.com) for transactional emails (verification, notifications). Resend offers **3,000 free emails/month** on their free tier.

### Why Resend?

- **Modern API** — Simple, developer-friendly REST API
- **Free Tier** — 3,000 emails/month at no cost
- **Works Everywhere** — Same behavior locally and in production
- **No SMTP** — No need to configure mail servers

### Setup Instructions

#### Step 1: Create a Resend Account

1. Go to [resend.com](https://resend.com) and sign up
2. Navigate to [API Keys](https://resend.com/api-keys) and create a new key
3. Copy the API key (starts with `re_`)

#### Step 2: Verify Your Domain

1. Go to [Domains](https://resend.com/domains) in Resend
2. Click "Add Domain" and enter your sending domain (e.g., `mail.yourdomain.com`)
3. Add the DNS records Resend provides:
   - **DKIM** — TXT record for email authentication
   - **SPF** — MX and TXT records for sender verification
4. Wait for verification (usually instant to a few minutes)

> **Tip:** Use a subdomain like `mail.yourdomain.com` to keep your main domain's DNS clean.

#### Step 3: Configure Open Feis

1. Log in as a **Super Admin** (e.g., `admin@openfeis.org`)
2. Go to **Admin** → **Settings**
3. Enter your configuration:
   - **Resend API Key:** Your `re_...` API key
   - **From Email:** Must match your verified domain (e.g., `Open Feis <noreply@mail.yourdomain.com>`)
   - **Site URL:** Your production URL (e.g., `https://yourdomain.com`) or `http://localhost:5173` for local dev
4. Click **Save Settings**

The status badge will change from "Not Configured" to "Configured" ✅

### Local Development

For local testing, you have two options:

**Option 1: Use Resend's Test Sender**
- Set From Email to: `Delivered <onboarding@resend.dev>`
- Emails will be sent but may go to spam

**Option 2: Skip Email Configuration**
- Leave the API key empty
- The app works without email — verification is skipped
- Users can still register and log in

### How Email Verification Works

1. User registers → verification email is sent (if configured)
2. User clicks link in email → email is verified
3. A banner shows for unverified users with a "Resend email" button
4. Verification links expire after 24 hours
5. Resending is rate-limited to once per 60 seconds

---

## 📖 User Guides

### For Parents: Managing Your Account

1. **Create an account** by clicking **"Register"** in the navigation
2. **Log in** with your email and password
3. **Access your account** by clicking your name in the navigation bar
4. **Manage your profile:**
   - Edit your name
   - Change your password
   - View email verification status
5. **Add dancer profiles:**
   - Click **"Add Dancer"** in the My Dancers section
   - Link your dancer to their teacher/school (searchable dropdown)
   - These profiles persist and can be used across multiple feiseanna
   - Teachers can see linked dancers in their Teacher Dashboard

### For Parents: Registering Your Dancer

1. Click **"Register"** in the navigation
2. **Select a Feis** to register for
3. **Select a Dancer:**
   - Choose from your saved dancers, OR
   - Click **"Add a New Dancer"** to create a new profile
4. **Create a Dancer Profile** (if adding new):
   - Enter your dancer's name
   - Enter their date of birth — the system automatically calculates their **competition age** (age as of January 1st)
   - Select their category (Girl/Boy)
   - Select their current level (First Feis, Beginner 1, Beginner 2, Novice, Prizewinner, Prelim Champ, Open Champ)
5. **Select Competitions (Enhanced Dance-by-Dance Grid):** 🆕
   - **Solo Dances:** See all 7 standard dances (Reel, Light Jig, Slip Jig, Single Jig, Treble Jig, Hornpipe, Traditional Set) in a grid
   - **Per-Dance Levels:** Each dance has a dropdown — adjust levels individually if your dancer is at different levels for different dances
   - **Toggle Selection:** Click the checkbox next to each dance to add/remove it from your cart
   - **Figure Dances:** Team dances (2-hand through 8-hand) are shown by age group only — no level selection needed
   - **Championships:** If eligible, register for Preliminary or Open Championship with one click
6. **Review Cart:**
   - See itemized fee breakdown
   - **Family Cap** automatically applies if you exceed $150
7. **Checkout** — Choose your payment method:
   - **Pay Now** — Complete payment online via Stripe
   - **Pay at Door** — Reserve your spot and pay at check-in on feis day

> **Tip:** Dancer profiles are saved to your account! When registering for future feiseanna, you can simply select your saved dancers instead of re-entering their information.

> **Tip:** The per-dance level settings are remembered, so if your dancer advances in one dance but not others, you can set each level appropriately.

### For Judges: Scoring a Round

1. Click **"Judge"** in the navigation
2. You'll see a list of competitors in the current round
3. **Tap a competitor** to open the scoring screen
4. **Enter the raw score** (0-100) and tap **"Save Score"**
5. If you lose internet:
   - A warning banner appears: "⚠ Saving Locally"
   - Your scores are saved to IndexedDB
   - When connectivity returns, scores sync automatically

### For Organizers: Creating a Feis

1. **Click "Admin"** in the frontend navigation
2. **Create a new Feis:**
   - Click "New Feis" button
   - Enter name, date, location
   - Click "Create"
3. **Manage Your Feis:**
   - Click "Manage" on any feis to see sub-options:
     - **Registrations** — View entries, assign competitor numbers, mark payments
     - **Competitions** — View, filter, edit, or delete competitions
     - **Generate Syllabus** — Auto-create competitions using the matrix builder
4. **Generate Syllabus:**
   - Select age range, levels, categories, and dances
   - Preview the competitions to be generated
   - Click "Generate" — competitions are created instantly

> **Note:** Administrative operations are handled in the Vue frontend (Admin tab) and the `/api/v1/admin/*` API endpoints.

### For Organizers: Using the Instant Scheduler 🆕

The **Instant Scheduler** generates a complete draft schedule with one click, following conventional North American feis patterns.

1. **Open Schedule Builder:**
   - Go to **Admin** → **Manage Feis** → **Schedule Builder**
   - Create stages if you haven't already (e.g., "Stage A", "Stage B")

2. **Click "Instant Scheduler"** (amber button in header)

3. **Configure Options** (or use defaults):
   - **Min/Max Competition Size** — Small competitions merge up, large ones split
   - **Feis Start/End Time** — Operating hours for the venue
   - **Lunch Window** — When lunch breaks should be inserted
   - **Default Durations** — Planning estimates for competitions without entries yet

4. **Click "Generate Schedule"**

5. **Review the Summary:**
   - **Merges** — Small competitions merged (younger dancers compete up)
   - **Splits** — Large competitions divided into Group A/B
   - **Warnings** — Conflicts or capacity issues to review

6. **Fine-tune in the Timeline:**
   - Drag competitions to adjust placement
   - The schedule is fully editable after generation
   - Click **Save Schedule** when satisfied

**Merge Rules:**
- Only younger dancers compete **up** (e.g., U8 → U9)
- Older dancers **never** move down to younger age groups
- 1-year merge preferred, 2-year merge optional (configurable)

**Split Rules:**
- Competitions exceeding max size (default 25) split into A/B groups
- Random assignment by default

> **Tip:** Run the Instant Scheduler early in planning (before registration closes) using the default durations. Re-run after registration with actual entry counts for more accurate time estimates.

### For Tabulators: Viewing Results

1. Click **"Tabulator"** in the navigation
2. **Select a Feis** from the dropdown (or leave as "All Feiseanna")
3. **Select a Competition** — only competitions with submitted scores appear
4. View results ranked by **Irish Points** with:
   - Competitor numbers and dancer names
   - Medal-style rank badges (gold/silver/bronze for top 3)
   - **Recall** status — green badge shows who advances to finals
5. Results **auto-refresh every 5 seconds** (toggle on/off)
6. Click **Refresh** for immediate update

> **Note:** The Tabulator is public — anyone can view results without logging in.

---

## 🧮 Irish Points Scoring Logic

Open Feis implements the official CLRG (An Coimisiún Le Rincí Gaelacha) scoring system.

### Conversion Table

| Place | Points | Place | Points |
|-------|--------|-------|--------|
| 1st | 100 | 6th | 53 |
| 2nd | 75 | 7th | 50 |
| 3rd | 65 | 8th | 47 |
| 4th | 60 | 9th | 45 |
| 5th | 56 | 10th | 43 |

Points continue to decrease until 50th place (1 point). 51st+ receive 0 points.

### Tie-Breaking (Split Points)

When dancers tie for a placement:
1. Sum the points for all tied positions
2. Divide by the number of tied dancers
3. Each tied dancer receives the averaged points

**Example:** Two dancers tie for 2nd place
- Points available: 75 (2nd) + 65 (3rd) = 140
- Each dancer receives: 140 ÷ 2 = **70 points**
- Next dancer is ranked 4th (60 points)

### Drop High/Low (5-Judge Panels)

For major championships with 5 judges:
1. Calculate Irish Points from each judge independently
2. For each dancer, identify the highest and lowest point totals
3. Discard these outliers
4. Sum the remaining 3 scores for final placement

### Competition Age (January 1st Rule)

A dancer's competition age is their age as of **January 1st of the competition year**, not their current age. This is standard across Irish Dance organizations.

---

## 🗃️ Database Models

### Core Models

```python
class User:
    id: UUID
    email: str
    password_hash: str
    role: RoleType  # super_admin, organizer, teacher, parent, adjudicator
    name: str
    email_verified: bool
    email_verification_token: Optional[str]
    email_verification_sent_at: Optional[datetime]

class SiteSettings:  # Singleton for admin-configurable settings
    id: int  # Always 1
    resend_api_key: Optional[str]
    resend_from_email: str
    site_name: str
    site_url: str

class Feis:
    id: UUID
    organizer_id: UUID  # FK to User
    name: str
    date: date
    location: str
    stripe_account_id: Optional[str]

class Dancer:
    id: UUID
    parent_id: UUID  # FK to User
    school_id: Optional[UUID]  # FK to User (teacher)
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str]
    is_adult: bool  # 🆕 Adult competitor flag
    # Per-dance level overrides (Enhanced Registration) 🆕
    level_reel: Optional[CompetitionLevel]
    level_light_jig: Optional[CompetitionLevel]
    level_slip_jig: Optional[CompetitionLevel]
    level_single_jig: Optional[CompetitionLevel]
    level_treble_jig: Optional[CompetitionLevel]
    level_hornpipe: Optional[CompetitionLevel]
    level_traditional_set: Optional[CompetitionLevel]
    # Note: Figure dances are not leveled — they're matched by age only

class Stage:
    id: UUID
    feis_id: UUID  # FK to Feis
    name: str  # e.g., "Stage A", "Main Hall"
    color: Optional[str]  # Hex color for UI
    sequence: int  # Display order

class FeisOrganizer:  # 🆕 Phase 7 - Multi-Organizer Support
    id: UUID
    feis_id: UUID  # FK to Feis
    user_id: UUID  # FK to User (co-organizer)
    role: str  # "co_organizer", "assistant", "volunteer_coordinator"
    can_edit_feis: bool  # Edit feis details, settings
    can_manage_entries: bool  # Manage registrations
    can_manage_schedule: bool  # Edit schedule
    can_manage_adjudicators: bool  # Manage judge roster
    can_add_organizers: bool  # Only primary owner by default
    added_by: UUID  # FK to User
    added_at: datetime

class FeisAdjudicator:  # 🆕 Phase 6 - Adjudicator Roster
    id: UUID
    feis_id: UUID  # FK to Feis
    user_id: Optional[UUID]  # FK to User (null until they accept invite)
    name: str  # Required even without account
    email: Optional[str]  # For sending invites
    phone: Optional[str]
    credential: Optional[str]  # e.g., "TCRG", "ADCRG"
    organization: Optional[str]  # e.g., "CLRG", "CRN"
    school_affiliation_id: Optional[UUID]  # FK to teacher for conflict detection
    status: AdjudicatorStatus  # invited, confirmed, active, declined
    invite_token: Optional[str]  # Magic link token
    access_pin_hash: Optional[str]  # Day-of PIN (hashed)

class StageJudgeCoverage:  # 🆕 Phase 6 - Time-based judge assignment
    id: UUID
    stage_id: UUID  # FK to Stage
    feis_adjudicator_id: UUID  # FK to FeisAdjudicator
    feis_day: date  # Which day of the feis
    start_time: time  # e.g., 09:00
    end_time: time  # e.g., 12:30
    note: Optional[str]  # e.g., "Grades only"

class Competition:
    id: UUID
    feis_id: UUID  # FK to Feis
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel  # first_feis, beginner_1, beginner_2, novice, prizewinner, preliminary_championship, open_championship
    gender: Optional[Gender]
    code: Optional[str]  # Auto-generated display code (e.g., "407SJ")
    max_entries: Optional[int]  # Per-competition cap
    category: CompetitionCategory  # SOLO, FIGURE, or CHAMPIONSHIP 🆕
    is_mixed: bool  # For mixed-gender figure dances 🆕
    # Scheduling fields
    dance_type: Optional[DanceType]  # REEL, LIGHT_JIG, SLIP_JIG, SINGLE_JIG, TWO_HAND, etc.
    tempo_bpm: Optional[int]  # Beats per minute
    bars: int  # Number of bars danced (default 48)
    scoring_method: ScoringMethod  # SOLO or CHAMPIONSHIP
    stage_id: Optional[UUID]  # FK to Stage
    scheduled_time: Optional[datetime]
    estimated_duration_minutes: Optional[int]
    adjudicator_id: Optional[UUID]  # FK to User

class Entry:
    id: UUID
    dancer_id: UUID
    competition_id: UUID
    competitor_number: Optional[int]
    paid: bool
    pay_later: bool  # "Pay at Door" registration
    order_id: Optional[UUID]  # FK to Order
    # Check-in fields 🆕
    check_in_status: CheckInStatus  # not_checked_in, checked_in, scratched
    checked_in_at: Optional[datetime]
    checked_in_by: Optional[UUID]  # FK to User

class FeisSettings:
    id: UUID
    feis_id: UUID  # FK to Feis (unique)
    base_entry_fee_cents: int  # e.g., 2500 = $25.00
    per_competition_fee_cents: int  # e.g., 1000 = $10.00
    family_max_cents: Optional[int]  # e.g., 15000 = $150.00
    late_fee_cents: int  # e.g., 500 = $5.00
    late_fee_date: Optional[date]
    change_fee_cents: int
    registration_opens: Optional[datetime]
    registration_closes: Optional[datetime]
    # Capacity & waitlist fields 🆕
    global_dancer_cap: Optional[int]  # Max total dancers for the feis
    enable_waitlist: bool  # Whether to allow waitlisting
    waitlist_offer_hours: int  # Hours for offer to be valid (default 48)

class FeeItem:  # 🆕 Phase 3
    id: UUID
    feis_id: UUID  # FK to Feis
    name: str  # e.g., "Venue Levy", "Program Book"
    amount_cents: int
    category: FeeCategory  # QUALIFYING or NON_QUALIFYING
    required: bool  # Auto-add to every order

class Order:  # 🆕 Phase 3
    id: UUID
    feis_id: UUID
    parent_id: UUID  # FK to User
    order_date: datetime
    total_cents: int
    status: PaymentStatus  # PENDING, PAID, REFUNDED, FAILED
    stripe_checkout_session_id: Optional[str]

class OrderItem:
    id: UUID
    order_id: UUID  # FK to Order
    description: str
    amount_cents: int
    category: FeeCategory  # Track which items count toward cap

class WaitlistEntry:  # 🆕 Phase 4.5
    id: UUID
    dancer_id: UUID  # FK to Dancer
    competition_id: Optional[UUID]  # FK to Competition (for comp-specific waitlist)
    feis_id: UUID  # FK to Feis (for global feis waitlist)
    status: WaitlistStatus  # waiting, promoted, expired, cancelled
    position: Optional[int]  # Position in queue
    offered_at: Optional[datetime]  # When a spot was offered
    expires_at: Optional[datetime]  # When the offer expires
    created_at: datetime

class RefundLog:  # 🆕 Phase 4.5
    id: UUID
    order_id: UUID  # FK to Order
    refund_amount_cents: int
    reason: str
    refunded_by: UUID  # FK to User
    refunded_at: datetime
    stripe_refund_id: Optional[str]
```

### Scoring Models

```python
class Round:
    id: str
    competition_id: UUID
    name: str
    sequence: int

class JudgeScore:
    id: UUID
    judge_id: str
    competitor_id: str  # Entry ID
    round_id: str       # Competition ID
    value: float        # Raw score (0-100)
    notes: Optional[str]  # Judge comments
    timestamp: datetime
```

---

## 🚢 Deployment

Open Feis uses Docker with Caddy for production deployment. Caddy provides automatic HTTPS via Let's Encrypt with zero configuration.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   your-domain.com                       │
│                         │                               │
│                    ┌────▼────┐                          │
│                    │  Caddy  │ ← Auto HTTPS (Let's Encrypt)
│                    │  :443   │                          │
│                    └────┬────┘                          │
│                         │                               │
│                    ┌────▼────┐                          │
│                    │ FastAPI │                          │
│                    │  :8000  │                          │
│                    └────┬────┘                          │
│                         │                               │
│                    ┌────▼────┐                          │
│                    │ SQLite  │                          │
│                    │  (WAL)  │                          │
│                    └─────────┘                          │
└─────────────────────────────────────────────────────────┘
```

### Prerequisites

- A Linux server (Debian/Ubuntu recommended)
- Docker and Docker Compose installed
- A domain name pointed to your server's IP
- Ports 80 and 443 open in your firewall

### Step 1: Provision a Server

**Google Cloud Platform (Free Tier):**
```bash
# Create an e2-micro instance (free tier eligible)
gcloud compute instances create openfeis-server \
  --machine-type=e2-micro \
  --zone=us-east1-c \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --tags=http-server,https-server

# Reserve a static IP
gcloud compute addresses create openfeis-ip --region=us-east1
```

**Other options:** DigitalOcean ($4/mo), Hetzner (€3.79/mo), or any VPS provider.

### Step 2: Install Docker

```bash
# SSH into your server
gcloud compute ssh openfeis-server --zone=us-east1-c

# Install Docker (Debian/Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### Step 3: Clone and Configure

```bash
# Create app directory
sudo mkdir -p /opt/openfeis
sudo chown $USER:$USER /opt/openfeis
cd /opt/openfeis

# Clone the repository
git clone https://github.com/OpenFeis/openfeis-server.git .

# Edit the Caddyfile to use YOUR domain
nano Caddyfile
# Replace "openfeis.org" with your domain name
```

**Example Caddyfile for your domain:**
```
yourdomain.com {
    reverse_proxy app:8000
    encode gzip zstd
}

www.yourdomain.com {
    redir https://yourdomain.com{uri} permanent
}
```

### Step 4: Deploy

> **Recommended environment variables (production):**
> - `OPENFEIS_JWT_SECRET`: long random string used to sign JWTs (keep stable across restarts)
> - `OPENFEIS_SEED_ADMIN_PASSWORD`: initial super-admin password on first boot

```bash
# Build and start the containers
docker compose up -d --build

# Check that everything is running
docker compose ps

# View logs
docker compose logs -f
```

### Step 5: Verify

Visit `https://yourdomain.com` — you should see the Open Feis homepage with a valid SSL certificate!

**Initial admin credentials:**
- Email: `admin@openfeis.org` (or `OPENFEIS_SEED_ADMIN_EMAIL`)
- Password: set via `OPENFEIS_SEED_ADMIN_PASSWORD` (recommended) or check server logs for the generated initial password

> ⚠️ **Important:** Change the admin password immediately after first login!

### Continuous Deployment

Pushing to `main` triggers automatic deployment via GitHub Actions:

1. **Build**: Docker image is built on GitHub's servers (avoids RAM constraints on small VMs)
2. **Push**: Image is pushed to GitHub Container Registry (`ghcr.io/openfeis/openfeis-server`)
3. **Deploy**: Server pulls the pre-built image and restarts services

No manual steps required — just push to `main`.

**Manual deployment** (if needed):
```bash
cd /opt/openfeis
git pull origin main
docker compose pull
docker compose up -d
```

### Deployment Files

| File | Purpose |
|------|---------|
| `.github/workflows/deploy.yml` | CI/CD pipeline (build image, push to registry, deploy) |
| `Dockerfile` | Multi-stage build (Node for frontend, Python for backend) |
| `docker-compose.yml` | Orchestrates Caddy + App containers (pulls from ghcr.io) |
| `Caddyfile` | Reverse proxy config with automatic HTTPS |
| `.dockerignore` | Excludes unnecessary files from Docker build |

### Infrastructure Costs

| Component | Specification | Cost |
|-----------|--------------|------|
| Compute | GCP `e2-micro` (2 vCPU, 1GB RAM) | Free tier |
| Storage | 30GB SSD | Free tier |
| SSL | Caddy + Let's Encrypt | Free |
| Email | Resend (3,000 emails/month) | Free tier |
| CI/CD | GitHub Actions (public repo) | Free |
| Container Registry | ghcr.io (public images) | Free |
| **Total** | | **$0/month** |

### Scaling Strategy

1. **Start:** `e2-micro` with swap enabled
2. **If RAM > 80%:** Upgrade to `e2-small` (2GB RAM, ~$13/mo)
3. **High traffic:** Add Cloudflare for CDN + DDoS protection (free tier)

### Database Migrations

Open Feis uses **automatic schema migrations** that run on server startup. No manual migration commands are required.

**How it works:**
1. When the server starts, `create_db_and_tables()` runs
2. It checks each table for missing columns
3. New columns are added with appropriate defaults
4. Data migrations run to fix any inconsistencies (e.g., enum case)

**Production deployment:**
- Push to `main` triggers the CI/CD pipeline
- The new Docker image is built and deployed
- On restart, migrations run automatically
- Existing data is preserved — new columns get sensible defaults

**No downtime required** for most schema changes. The migration system handles:
- Adding new columns with `ALTER TABLE ADD COLUMN`
- Setting default values for existing rows
- Fixing enum value casing (lowercase → uppercase)

> **Note:** SQLite doesn't support all ALTER TABLE operations. Dropping or renaming columns requires manual intervention (rare).

### Backup & Recovery

The SQLite database is stored in a Docker volume (`openfeis_data`). To backup:

```bash
# Create a backup
docker compose exec app cp /data/openfeis.db /data/backup-$(date +%Y%m%d).db

# Copy backup to local machine
docker cp openfeis-app-1:/data/backup-*.db ./backups/
```

**Planned:** Litestream integration for real-time streaming backups to cloud storage.

---

## 🏟️ Venue Deployment (Offline Mode)

For feiseanna with unreliable WiFi, Open Feis can run entirely on a local laptop:

```bash
# Start the local server (no internet required)
docker compose -f docker-compose.local.yml up
```

**How it works:**
1. Laptop runs Open Feis server on the venue WiFi network
2. Judges connect their tablets to the same network
3. Scores save locally and broadcast via WebSocket
4. Tabulator calculates results in real-time
5. After the event, sync everything to the cloud

See [`docs/venue-deployment.md`](docs/venue-deployment.md) for detailed setup instructions.

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- **Backend:** Follow PEP 8, use type hints
- **Frontend:** Use Composition API, TypeScript strict mode
- **Commits:** Use conventional commits (`feat:`, `fix:`, `docs:`)

---

## ⚖️ Legal & Compliance

### Clean Room Implementation

All scoring logic is derived **strictly** from the official [CLRG Rules & Regulations Handbook](https://www.clrg.ie). No proprietary code from competing platforms was observed or reverse-engineered.

### Trademark

"Open Feis" is an original name. We do not use terms like "Go", "Quick", or "Worx" that might cause confusion with existing platforms.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.