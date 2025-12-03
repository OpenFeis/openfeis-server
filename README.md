# ☘️ Open Feis

**A modern, local-first Irish Dance competition management platform.**

Open Feis is an open-source alternative to legacy feis management systems. Built with resilience at its core, it guarantees data integrity and operational continuity—even during internet outages. No more "tabulation meltdowns."

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
- **Demo Mode** — Explore the interface before creating an account

### For Parents & Guardians
- **Self-Service Registration** — Create your own account instantly
- **Dancer Profiles** — Store your children's info with automatic competition age calculation (January 1st rule)
- **Smart Registration** — Only see competitions your dancer is eligible for (filtered by age, gender, level)
- **Family Cap** — Never pay more than $150 per feis, no matter how many competitions
- **Multi-Dancer Support** — Register siblings in one transaction

### For Judges (Adjudicators)
- **Offline Scoring** — Score dancers even when WiFi drops; syncs when connectivity returns
- **Clean Interface** — Large touch targets designed for iPad use at stage-side
- **Automatic Backup** — Scores saved locally to IndexedDB, then synced to server
- **Secure Access** — Only adjudicators can submit scores

### For Organizers
- **Feis Manager** — Create, edit, and manage feiseanna from the frontend (no SQL required)
- **Syllabus Generator** — Auto-generate 100+ competitions with one click (Age × Gender × Level × Dance)
- **Competition Manager** — View, filter, and manage all competitions in a feis
- **Entry Manager** — Assign competitor numbers, mark payments, track registrations
- **Site Settings** — Configure email (Resend API key) and site-wide settings (Super Admin only)
- **Admin Panel** — Fallback CRUD interface via `sqladmin` for edge cases
- **Tabulator Dashboard** — Real-time results with Irish Points, Drop High/Low, and recall calculations
- **Protected Operations** — Only organizers can modify their own feiseanna

### For Tabulators
- **Live Results** — See scores as judges submit them
- **Irish Points Engine** — Automatic conversion from raw scores to CLRG Irish Points
- **Tie-Breaking** — Proper "split points" algorithm for tied placements
- **Drop High/Low** — Support for 5-judge panels with automatic outlier removal

---

## 🏗️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.11, FastAPI | High performance, async, auto-generated OpenAPI docs |
| **Database** | SQLite (WAL mode) | Zero network latency, 10k+ reads/sec, single-file simplicity |
| **ORM** | SQLModel (SQLAlchemy) | Type-safe models with Pydantic validation |
| **Auth** | JWT + bcrypt (passlib, python-jose) | Stateless auth, secure password hashing |
| **Email** | Resend | Transactional emails (verification, notifications) |
| **Admin** | sqladmin | Auto-generated CRUD interface |
| **Frontend** | Vue 3, TypeScript, Vite | Modern reactivity with Composition API |
| **Styling** | Tailwind CSS v4 | Utility-first, highly customizable |
| **State** | Pinia | Official Vue state management |
| **Offline** | IndexedDB (idb) | Local-first architecture for judge scoring |

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
- **Admin Panel (sqladmin):** http://localhost:8000/admin

> **Note:** The frontend dev server proxies `/api` requests to the backend automatically via `vite.config.ts`.

### Initial Data

On first run, the database is seeded with:
- A Super Admin user (`admin@openfeis.org` / `admin123`)
- A sample feis ("Great Irish Feis 2025")
- A sample competition

> **Demo Credentials:** Email: `admin@openfeis.org` Password: `admin123`

---

## 📁 Project Structure

```
openfeis-server/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── admin.py                # sqladmin configuration
│   ├── api/
│   │   ├── auth.py             # Authentication utilities (JWT, password hashing)
│   │   ├── routes.py           # API endpoints
│   │   └── schemas.py          # Pydantic request/response models
│   ├── db/
│   │   └── database.py         # SQLite connection & session
│   ├── services/
│   │   ├── email.py            # Email service (Resend integration)
│   │   └── number_cards.py     # PDF generation for competitor numbers
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
│   │   │   │   └── SiteSettings.vue        # Email & site configuration
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
│   │   │   │   ├── EligibilityPicker.vue
│   │   │   │   └── CartSummary.vue
│   │   │   └── tabulator/
│   │   │       └── TabulatorDashboard.vue
│   │   ├── models/
│   │   │   └── types.ts        # TypeScript interfaces
│   │   ├── services/
│   │   │   └── db.ts           # IndexedDB for offline storage
│   │   └── stores/
│   │       ├── auth.ts         # Pinia store for authentication
│   │       └── scoring.ts      # Pinia store for scores
│   └── package.json
├── tests/
│   └── test_recall.py          # Unit tests
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Container orchestration
├── Caddyfile                   # Reverse proxy + HTTPS config
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

### Feis Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/api/v1/feis` | Create a new feis | Organizer/Admin |
| `GET` | `/api/v1/feis` | List all feiseanna | No |
| `GET` | `/api/v1/feis/{id}` | Get a single feis | No |
| `PUT` | `/api/v1/feis/{id}` | Update a feis | Owner/Admin |
| `DELETE` | `/api/v1/feis/{id}` | Delete a feis | Owner/Admin |

### Competition Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/feis/{feis_id}/competitions` | Create competition for a feis |
| `GET` | `/api/v1/feis/{feis_id}/competitions` | List competitions in a feis |
| `GET` | `/api/v1/competitions/{id}` | Get a single competition |
| `PUT` | `/api/v1/competitions/{id}` | Update a competition |
| `DELETE` | `/api/v1/competitions/{id}` | Delete a competition |

### Entry Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/entries` | Create an entry |
| `GET` | `/api/v1/entries` | List all entries |
| `GET` | `/api/v1/entries/{id}` | Get a single entry |
| `PUT` | `/api/v1/entries/{id}` | Update an entry (set number, mark paid) |
| `DELETE` | `/api/v1/entries/{id}` | Delete an entry |

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

### Example: Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@openfeis.org",
    "password": "admin123"
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
    "levels": ["beginner", "novice", "prizewinner"],
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

### For Parents: Registering Your Dancer

1. **Create an account** by clicking **"Register"** in the navigation
2. **Log in** with your email and password
3. **Navigate to the app** and click **"Register"** to add dancers
2. **Create a Dancer Profile:**
   - Enter your dancer's name
   - Enter their date of birth — the system automatically calculates their **competition age** (age as of January 1st)
   - Select their category (Girl/Boy)
   - Select their current level (Beginner, Novice, Prizewinner, Championship)
3. **Select Competitions:**
   - The system only shows competitions your dancer is **eligible** for
   - Competitions are grouped by dance type (Reel, Light Jig, etc.)
   - Click to select/deselect
4. **Review Cart:**
   - See itemized fee breakdown
   - **Family Cap** automatically applies if you exceed $150
5. **Checkout** (Stripe integration coming soon)

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

> **Note:** The `sqladmin` panel at `/admin` is available for edge cases but most operations are now handled in the frontend.

### For Tabulators: Viewing Results

1. Click **"Tabulator"** in the navigation
2. Select a round from the dropdown
3. View results ranked by **Irish Points**
4. Results update in real-time as judges submit scores

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
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str]

class Competition:
    id: UUID
    feis_id: UUID  # FK to Feis
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender]

class Entry:
    id: UUID
    dancer_id: UUID
    competition_id: UUID
    competitor_number: Optional[int]
    paid: bool
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
    competitor_id: str
    round_id: str
    value: float  # Raw score (0-100)
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

**Default admin credentials:**
- Email: `admin@openfeis.org`
- Password: `admin123`

> ⚠️ **Important:** Change the admin password immediately after first login!

### Updating

To deploy updates from GitHub:

```bash
cd /opt/openfeis
./deploy.sh
```

Or manually:
```bash
git pull origin main
docker compose build --no-cache
docker compose up -d
docker image prune -f
```

### Deployment Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (Node for frontend, Python for backend) |
| `docker-compose.yml` | Orchestrates Caddy + App containers |
| `Caddyfile` | Reverse proxy config with automatic HTTPS |
| `.dockerignore` | Excludes unnecessary files from Docker build |
| `deploy.sh` | One-command deployment script |

### Infrastructure Costs

| Component | Specification | Cost |
|-----------|--------------|------|
| Compute | GCP `e2-micro` (2 vCPU, 1GB RAM) | Free tier |
| Storage | 30GB SSD | Free tier |
| SSL | Caddy + Let's Encrypt | Free |
| Email | Resend (3,000 emails/month) | Free tier |
| **Total** | | **$0/month** |

### Scaling Strategy

1. **Start:** `e2-micro` with swap enabled
2. **If RAM > 80%:** Upgrade to `e2-small` (2GB RAM, ~$13/mo)
3. **High traffic:** Add Cloudflare for CDN + DDoS protection (free tier)

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

## 🗺️ Roadmap

### ✅ Completed (Phase 1, 2 & 3)

- [x] Irish Points Calculator with tie-breaking
- [x] Drop High/Low for 5-judge panels
- [x] Offline-capable Judge Pad
- [x] Tabulator Dashboard with live results
- [x] SQLite database with SQLModel
- [x] Admin panel (sqladmin fallback)
- [x] Dancer Profile with competition age calculation
- [x] Eligibility-filtered competition picker
- [x] Cart with Family Cap logic
- [x] Syllabus Generator (matrix builder)
- [x] Frontend Feis Manager (CRUD)
- [x] Frontend Competition Manager
- [x] Frontend Entry Manager (number assignment, payment tracking)
- [x] Full REST API for Feis, Competition, Entry
- [x] **User Authentication** — JWT-based login/logout with secure password hashing
- [x] **User Registration** — Self-service account creation (default role: parent)
- [x] **Role-Based Access Control** — Protected routes by user role (super_admin, organizer, adjudicator, parent, teacher)
- [x] **Number Card PDF** — Generate printable competitor numbers with QR codes for check-in
- [x] **Recall Calculator** — Auto-calculate top 50% for championships with tie extension
- [x] **Docker Deployment** — Production-ready containerization with Caddy reverse proxy
- [x] **Automatic HTTPS** — Let's Encrypt certificates via Caddy
- [x] **Email Verification** — Verify email addresses on registration (via Resend)
- [x] **Site Settings UI** — Admin-configurable email and site settings

### 🔜 Coming Soon (Phase 4)

- [ ] **Stripe Connect** — Payment processing
- [ ] **Teacher Portal** — Bulk registration & approval
- [ ] **Scheduling Matrix** — Drag-and-drop stage assignment
- [ ] **Digital Signage** — Stage-side displays for "Now Dancing / On Deck"
- [ ] **Audit Log** — Track every score change with timestamps

### 🔮 Future

- [ ] Native iOS/Android apps
- [ ] Multi-feis dashboard for organizations
- [ ] Historical results & dancer statistics
- [ ] Integration with CLRG Grade Exams

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

---

## 💚 Acknowledgments

Built with love for the Irish Dance community. Special thanks to:

- The CLRG for maintaining clear competition rules
- The teachers and parents who shared their frustrations with existing systems
- The adjudicators who tested offline scoring in the field

---

<p align="center">
  <strong>☘️ Sláinte! ☘️</strong><br>
  <em>May your hard shoe be loud and your soft shoe be light.</em>
</p>

