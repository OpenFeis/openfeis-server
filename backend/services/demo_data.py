"""
Demo Data Generator for Open Feis.

Creates realistic demo data for testing and demonstration purposes.
All demo data uses identifiable patterns for easy cleanup:
- Demo users have emails matching `demo_*@openfeis.demo`
- Demo feiseanna are owned by the demo organizer

Super Admin only feature.
"""

import random
from datetime import date, datetime, timedelta
from typing import List, Tuple, Optional
from uuid import uuid4, UUID
from sqlmodel import Session, select, delete

from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Entry, Dancer, Stage, FeisSettings,
    RoleType, CompetitionLevel, Gender, DanceType, ScoringMethod,
    CheckInStatus, PaymentStatus, Order, FeeItem, FeeCategory,
    PlacementHistory, StageJudgeCoverage, FeisAdjudicator
)
from backend.scoring_engine.models import JudgeScore
from backend.api.auth import hash_password
from backend.utils.competition_codes import generate_competition_code
from backend.services.scheduling import estimate_competition_duration, get_default_tempo

# ============= Constants =============

DEMO_EMAIL_DOMAIN = "openfeis.demo"
DEMO_ORGANIZER_EMAIL = f"demo_organizer@{DEMO_EMAIL_DOMAIN}"
DEMO_PASSWORD = "demo123"  # All demo accounts use this password

# Irish-flavored names for realism
GIRL_FIRST_NAMES = [
    "Siobhan", "Aoife", "Niamh", "Caoimhe", "Saoirse", "Ciara", "Aisling", 
    "Roisin", "Fionnuala", "Orlaith", "Maeve", "Sinead", "Grainne", "Deirdre",
    "Erin", "Keira", "Molly", "Bridget", "Colleen", "Shannon", "Kathleen",
    "Maureen", "Fiona", "Tara", "Riley", "Reagan", "Quinn", "Nora", "Caitlin",
    "Brenna", "Aislinn", "Keeva", "Sorcha", "Clodagh", "Eimear", "Laoise",
    "Brigid", "Cara", "Eilis", "Mairead", "Una", "Riona", "Catriona", "Eithne"
]

BOY_FIRST_NAMES = [
    "Cian", "Oisin", "Fionn", "Darragh", "Conor", "Sean", "Liam", "Padraig",
    "Eoin", "Cathal", "Declan", "Ronan", "Brendan", "Patrick", "Colin",
    "Ryan", "Kevin", "Brian", "Finn", "Aidan", "Kieran", "Niall", "Callum",
    "Seamus", "Cormac", "Lorcan", "Tadhg", "Ruairi", "Ciaran", "Donal",
    "Diarmuid", "Eoghan", "Fergal", "Gearoid", "Odhran", "Pearse", "Rory"
]

LAST_NAMES = [
    "O'Brien", "Murphy", "Kelly", "O'Connor", "Walsh", "Ryan", "O'Sullivan",
    "McCarthy", "Byrne", "Gallagher", "Doyle", "Lynch", "Murray", "Quinn",
    "Moore", "McLoughlin", "O'Neill", "Brennan", "Burke", "Collins",
    "Campbell", "Doherty", "Kennedy", "Fitzgerald", "Kavanagh", "Duffy",
    "Nolan", "Donnelly", "Regan", "O'Reilly", "Flanagan", "Connolly",
    "Maguire", "O'Donnell", "Carroll", "Healy", "Sheehan", "O'Leary",
    "Kearney", "Boyle", "Higgins", "McGrath", "Callaghan", "Fahey"
]

SCHOOL_NAMES = [
    "McTeggart Academy of Irish Dance",
    "Trinity Irish Dance Company", 
    "Mulhern School of Irish Dance",
    "Celtic Steps Academy",
    "Emerald Isle School of Dance",
    "Shamrock Dance Academy",
    "Claddagh Irish Dancers",
    "Tara Academy of Irish Dance",
    "Scoil Rince Ni Bhriain",
    "Keltic Dreams Dance Academy",
    "O'Shea-Chaplin Academy",
    "Cashel Dennehy School",
    "Rince na Chroi Academy",
    "Harp & Shamrock School",
    "Inishfree School of Irish Dance",
    "Cross Keys School of Irish Dance",
    "Drake School of Irish Dance",
    "Glencastle Irish Dancers",
    "Heritage Irish Dance Company"
]

FEIS_VENUE_TEMPLATES = [
    "{city} Convention Center",
    "{city} Marriott Hotel",
    "{city} Civic Auditorium", 
    "Hilton {city} Downtown",
    "{city} Irish Cultural Center",
    "Knights of Columbus Hall, {city}",
    "{city} Community Center"
]

CITIES = [
    "Chicago", "Boston", "Philadelphia", "Cleveland", "Detroit",
    "Minneapolis", "Denver", "Seattle", "Portland", "San Francisco",
    "Los Angeles", "Phoenix", "Dallas", "Houston", "Atlanta",
    "Charlotte", "Nashville", "St. Louis", "Milwaukee", "Indianapolis"
]

# Dance types for syllabus generation
STANDARD_DANCES = [
    DanceType.REEL,
    DanceType.LIGHT_JIG, 
    DanceType.SLIP_JIG,
    DanceType.TREBLE_JIG,
    DanceType.HORNPIPE,
]

# Level weights for realistic distribution (more beginners, fewer champs)
LEVEL_WEIGHTS = {
    CompetitionLevel.FIRST_FEIS: 0.05,
    CompetitionLevel.BEGINNER_1: 0.15,
    CompetitionLevel.BEGINNER_2: 0.15,
    CompetitionLevel.NOVICE: 0.25,
    CompetitionLevel.PRIZEWINNER: 0.20,
    CompetitionLevel.PRELIMINARY_CHAMPIONSHIP: 0.12,
    CompetitionLevel.OPEN_CHAMPIONSHIP: 0.08,
}

# Age distribution weights (bell curve around 10-12)
AGE_WEIGHTS = {
    5: 0.02, 6: 0.04, 7: 0.06, 8: 0.10, 9: 0.12,
    10: 0.14, 11: 0.14, 12: 0.12, 13: 0.10, 14: 0.08,
    15: 0.04, 16: 0.02, 17: 0.01, 18: 0.01
}


# ============= Helper Functions =============

def weighted_choice(weights: dict) -> any:
    """Select a random key based on weights."""
    items = list(weights.keys())
    probs = list(weights.values())
    return random.choices(items, weights=probs, k=1)[0]


def random_date_of_birth(competition_age: int, feis_date: date) -> date:
    """
    Generate a DOB for a dancer who will be `competition_age` on Jan 1 of feis year.
    Competition age = age on January 1st of the competition year.
    """
    competition_year = feis_date.year
    # They turn competition_age during the year they were born + competition_age
    birth_year = competition_year - competition_age
    
    # Random month/day, but ensure they're the right age on Jan 1
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)  # Safe for all months
    
    return date(birth_year, birth_month, birth_day)


def generate_dancer_name(gender: Gender) -> Tuple[str, str]:
    """Generate a realistic Irish dance name."""
    if gender == Gender.FEMALE:
        first = random.choice(GIRL_FIRST_NAMES)
    else:
        first = random.choice(BOY_FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last


def generate_feis_name(days_offset: int) -> str:
    """Generate a realistic feis name."""
    city = random.choice(CITIES)
    templates = [
        f"{city} Feis",
        f"Great {city} Irish Feis",
        f"{city} Irish Dance Festival",
        f"Emerald City Feis - {city}",
        f"{city} Celtic Championships",
    ]
    return random.choice(templates)


def generate_venue(city: str) -> str:
    """Generate a venue name for a city."""
    template = random.choice(FEIS_VENUE_TEMPLATES)
    return template.format(city=city)


# ============= Demo Data Generator Class =============

class DemoDataGenerator:
    """Generates comprehensive demo data for Open Feis."""
    
    def __init__(self, session: Session):
        self.session = session
        self.demo_organizer: Optional[User] = None
        self.demo_teachers: List[User] = []
        self.demo_parents: List[User] = []
        self.demo_dancers: List[Dancer] = []
        self.demo_feiseanna: List[Feis] = []
        self.demo_adjudicators: List[User] = []
    
    def generate_all(self) -> dict:
        """
        Generate all demo data.
        
        Returns summary of what was created.
        """
        summary = {
            "organizers": 0,
            "teachers": 0,
            "parents": 0,
            "adjudicators": 0,
            "dancers": 0,
            "feiseanna": 0,
            "competitions": 0,
            "entries": 0,
            "scores": 0,
        }
        
        # 1. Create demo users
        self._create_demo_organizer()
        summary["organizers"] = 1
        
        self._create_demo_teachers(count=12)
        summary["teachers"] = len(self.demo_teachers)
        
        self._create_demo_adjudicators(count=15)
        summary["adjudicators"] = len(self.demo_adjudicators)
        
        # 2. Create future feis #1 (60 days out, ~250 dancers)
        feis1, stats1 = self._create_feis_with_registrations(
            days_offset=60,
            target_dancers=250,
            name_override="Shamrock Classic Feis"
        )
        summary["feiseanna"] += 1
        summary["competitions"] += stats1["competitions"]
        summary["entries"] += stats1["entries"]
        summary["parents"] += stats1["parents"]
        summary["dancers"] += stats1["dancers"]
        
        # 3. Create future feis #2 (90 days out, ~103 dancers)
        feis2, stats2 = self._create_feis_with_registrations(
            days_offset=90,
            target_dancers=103,
            name_override="Celtic Pride Championships"
        )
        summary["feiseanna"] += 1
        summary["competitions"] += stats2["competitions"]
        summary["entries"] += stats2["entries"]
        summary["parents"] += stats2["parents"]
        summary["dancers"] += stats2["dancers"]
        
        # 4. Create past feis (7 days ago, ~350 dancers, with complete results)
        feis3, stats3 = self._create_completed_feis(
            days_offset=-7,
            target_dancers=350,
            name_override="Emerald Isle Fall Feis"
        )
        summary["feiseanna"] += 1
        summary["competitions"] += stats3["competitions"]
        summary["entries"] += stats3["entries"]
        summary["parents"] += stats3["parents"]
        summary["dancers"] += stats3["dancers"]
        summary["scores"] += stats3["scores"]
        
        self.session.commit()
        
        return summary
    
    def _create_demo_organizer(self):
        """Create the demo organizer account."""
        existing = self.session.exec(
            select(User).where(User.email == DEMO_ORGANIZER_EMAIL)
        ).first()
        
        if existing:
            self.demo_organizer = existing
            return
        
        self.demo_organizer = User(
            id=uuid4(),
            email=DEMO_ORGANIZER_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            role=RoleType.ORGANIZER,
            name="Demo Feis Organizer",
            email_verified=True
        )
        self.session.add(self.demo_organizer)
        self.session.flush()
    
    def _create_demo_teachers(self, count: int = 8):
        """Create demo teacher accounts with school names."""
        for i in range(count):
            email = f"demo_teacher_{i+1}@{DEMO_EMAIL_DOMAIN}"
            
            existing = self.session.exec(
                select(User).where(User.email == email)
            ).first()
            
            if existing:
                self.demo_teachers.append(existing)
                continue
            
            school_name = SCHOOL_NAMES[i % len(SCHOOL_NAMES)]
            teacher = User(
                id=uuid4(),
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=RoleType.TEACHER,
                name=school_name,  # Teacher name is the school name
                email_verified=True
            )
            self.session.add(teacher)
            self.demo_teachers.append(teacher)
        
        self.session.flush()
    
    def _create_demo_adjudicators(self, count: int = 6):
        """Create demo adjudicator accounts."""
        adjudicator_names = [
            "Judge Mary Catherine O'Malley, ADCRG",
            "Judge Patrick Seamus Walsh, ADCRG", 
            "Judge Brigid Anne Kelly, TCRG",
            "Judge Michael Brendan Murphy, ADCRG",
            "Judge Siobhan Rose Byrne, TCRG",
            "Judge Thomas Francis Quinn, ADCRG",
            "Judge Colm Padraig Doyle, ADCRG",
            "Judge Fiona Marie Gallagher, ADCRG",
            "Judge Seamus Patrick O'Neill, ADCRG",
            "Judge Kathleen Nora Ryan, ADCRG",
            "Judge Declan Joseph Kennedy, ADCRG",
            "Judge Eileen Maura Fitzgerald, TCRG",
            "Judge Liam Ciaran McCarthy, ADCRG",
            "Judge Aoife Niamh O'Sullivan, ADCRG",
            "Judge Cormac Eoin Murray, ADCRG"
        ]
        
        for i in range(count):
            email = f"demo_judge_{i+1}@{DEMO_EMAIL_DOMAIN}"
            
            existing = self.session.exec(
                select(User).where(User.email == email)
            ).first()
            
            if existing:
                self.demo_adjudicators.append(existing)
                continue
            
            adj_name = adjudicator_names[i % len(adjudicator_names)]
            adj = User(
                id=uuid4(),
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=RoleType.ADJUDICATOR,
                name=adj_name,
                email_verified=True
            )
            self.session.add(adj)
            self.demo_adjudicators.append(adj)
        
        self.session.flush()
    
    def _create_demo_parent(self, index: int) -> User:
        """Create a demo parent account."""
        email = f"demo_parent_{index}@{DEMO_EMAIL_DOMAIN}"
        
        existing = self.session.exec(
            select(User).where(User.email == email)
        ).first()
        
        if existing:
            return existing
        
        first, last = generate_dancer_name(random.choice([Gender.FEMALE, Gender.MALE]))
        parent = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=RoleType.PARENT,
            name=f"{first} {last}",
            email_verified=True
        )
        self.session.add(parent)
        self.session.flush()
        return parent
    
    def _create_feis_with_registrations(
        self,
        days_offset: int,
        target_dancers: int,
        name_override: Optional[str] = None
    ) -> Tuple[Feis, dict]:
        """
        Create a feis with full syllabus and registrations.
        
        Returns (feis, stats_dict)
        """
        stats = {"competitions": 0, "entries": 0, "parents": 0, "dancers": 0}
        
        feis_date = date.today() + timedelta(days=days_offset)
        city = random.choice(CITIES)
        
        feis = Feis(
            id=uuid4(),
            organizer_id=self.demo_organizer.id,
            name=name_override or generate_feis_name(days_offset),
            date=feis_date,
            location=generate_venue(city)
        )
        self.session.add(feis)
        self.session.flush()
        self.demo_feiseanna.append(feis)
        
        # Create feis settings
        settings = FeisSettings(
            id=uuid4(),
            feis_id=feis.id,
            base_entry_fee_cents=2500,
            per_competition_fee_cents=1200,
            family_max_cents=17500,
            late_fee_cents=500,
            late_fee_date=feis_date - timedelta(days=14),
            registration_opens=datetime.now() - timedelta(days=30),
            registration_closes=datetime.combine(feis_date - timedelta(days=3), datetime.min.time()),
        )
        self.session.add(settings)
        
        # Create stages
        stages = self._create_stages(feis.id, count=4)
        
        # Create competitions (full syllabus)
        competitions = self._create_syllabus(feis, stages)
        stats["competitions"] = len(competitions)
        
        # Create dancers and registrations
        parent_count = 0
        dancer_count = 0
        entry_count = 0
        
        # Determine family structure (some parents have multiple dancers)
        num_families = int(target_dancers * 0.7)  # ~70% single-dancer families
        remaining = target_dancers - num_families
        
        # Create single-dancer families
        for i in range(num_families):
            parent = self._create_demo_parent(len(self.demo_parents) + i + 1)
            self.demo_parents.append(parent)
            parent_count += 1
            
            dancer, entries = self._create_dancer_with_entries(
                parent, feis, competitions, dancer_index=dancer_count
            )
            dancer_count += 1
            entry_count += len(entries)
        
        # Create multi-dancer families (2-3 dancers each)
        family_idx = num_families
        while dancer_count < target_dancers:
            parent = self._create_demo_parent(len(self.demo_parents) + family_idx + 1)
            self.demo_parents.append(parent)
            parent_count += 1
            family_idx += 1
            
            num_siblings = min(random.randint(2, 3), target_dancers - dancer_count)
            for _ in range(num_siblings):
                dancer, entries = self._create_dancer_with_entries(
                    parent, feis, competitions, dancer_index=dancer_count
                )
                dancer_count += 1
                entry_count += len(entries)
        
        stats["parents"] = parent_count
        stats["dancers"] = dancer_count
        stats["entries"] = entry_count
        
        # Assign competitor numbers
        self._assign_competitor_numbers(feis.id)
        
        # Create schedule - SKIPPED for realism as per request
        # self._create_schedule(feis, stages, competitions)
        
        return feis, stats
    
    def _create_completed_feis(
        self,
        days_offset: int,
        target_dancers: int,
        name_override: Optional[str] = None
    ) -> Tuple[Feis, dict]:
        """
        Create a past feis with complete results (scores, placements).
        """
        feis, stats = self._create_feis_with_registrations(
            days_offset=days_offset,
            target_dancers=target_dancers,
            name_override=name_override
        )
        
        # Mark all entries as checked in and paid
        entries = self.session.exec(
            select(Entry)
            .join(Competition)
            .where(Competition.feis_id == feis.id)
        ).all()
        
        for entry in entries:
            entry.paid = True
            entry.check_in_status = CheckInStatus.CHECKED_IN
            entry.checked_in_at = datetime.combine(feis.date, datetime.min.time()) + timedelta(hours=8)
            self.session.add(entry)
        
        # Generate scores for all competitions
        score_count = self._generate_scores_for_feis(feis)
        stats["scores"] = score_count
        
        return feis, stats
    
    def _create_stages(self, feis_id: UUID, count: int = 4) -> List[Stage]:
        """Create stages for a feis."""
        stage_configs = [
            ("Main Stage", "#6366f1"),  # Indigo
            ("Stage B", "#ec4899"),      # Pink
            ("Stage C", "#14b8a6"),      # Teal
            ("Stage D", "#f59e0b"),      # Amber
            ("Championship Hall", "#8b5cf6"),  # Purple
            ("Beginner Area", "#22c55e"),  # Green
        ]
        
        stages = []
        for i in range(min(count, len(stage_configs))):
            name, color = stage_configs[i]
            stage = Stage(
                id=uuid4(),
                feis_id=feis_id,
                name=name,
                color=color,
                sequence=i
            )
            self.session.add(stage)
            stages.append(stage)
        
        self.session.flush()
        return stages
    
    def _create_syllabus(self, feis: Feis, stages: List[Stage]) -> List[Competition]:
        """Create a full competition syllabus."""
        competitions = []
        
        # Age groups
        age_groups = [
            (5, 6, "U7"),
            (7, 7, "U8"),
            (8, 8, "U9"),
            (9, 9, "U10"),
            (10, 10, "U11"),
            (11, 11, "U12"),
            (12, 12, "U13"),
            (13, 14, "U15"),
            (15, 17, "U18"),
            (18, 99, "18 & Over"),
        ]
        
        # Levels to include
        levels = [
            CompetitionLevel.BEGINNER_1,
            CompetitionLevel.BEGINNER_2,
            CompetitionLevel.NOVICE,
            CompetitionLevel.PRIZEWINNER,
            CompetitionLevel.PRELIMINARY_CHAMPIONSHIP,
            CompetitionLevel.OPEN_CHAMPIONSHIP,
        ]
        
        # Standard dances for each level
        for level in levels:
            # Championship levels get combined competitions (no per-dance events)
            if level in [CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP]:
                scoring = ScoringMethod.CHAMPIONSHIP
                
                for min_age, max_age, age_label in age_groups:
                    # Skip very young for championship
                    if min_age < 10:
                        continue
                        
                    # Create one competition per age/gender (dancers perform 3 rounds inside this)
                    # Girls
                    comp_girls = self._create_competition(
                        feis, level, min_age, max_age, Gender.FEMALE, None, scoring, stages
                    )
                    competitions.append(comp_girls)
                    
                    # Boys (combined age groups if needed, but keeping separate for now)
                    comp_boys = self._create_competition(
                        feis, level, min_age, max_age, Gender.MALE, None, scoring, stages
                    )
                    competitions.append(comp_boys)
                    
            else:
                # Grades levels (per dance)
                dances = [DanceType.REEL, DanceType.LIGHT_JIG, DanceType.SLIP_JIG]
                scoring = ScoringMethod.SOLO
            
                for min_age, max_age, age_label in age_groups:
                    for dance in dances:
                        # Girls competition
                        comp_girls = self._create_competition(
                            feis, level, min_age, max_age, Gender.FEMALE, dance, scoring, stages
                        )
                        competitions.append(comp_girls)
                        
                        # Boys competition (combined for smaller numbers at younger ages)
                        if min_age >= 8 or level in [CompetitionLevel.NOVICE, CompetitionLevel.PRIZEWINNER]:
                            comp_boys = self._create_competition(
                                feis, level, min_age, max_age, Gender.MALE, dance, scoring, stages
                            )
                            competitions.append(comp_boys)
        
        self.session.flush()
        return competitions
    
    def _create_competition(
        self,
        feis: Feis,
        level: CompetitionLevel,
        min_age: int,
        max_age: int,
        gender: Gender,
        dance_type: Optional[DanceType],
        scoring_method: ScoringMethod,
        stages: List[Stage]
    ) -> Competition:
        """Create a single competition."""
        # Generate name
        level_names = {
            CompetitionLevel.FIRST_FEIS: "First Feis",
            CompetitionLevel.BEGINNER_1: "Beginner 1",
            CompetitionLevel.BEGINNER_2: "Beginner 2",
            CompetitionLevel.NOVICE: "Novice",
            CompetitionLevel.PRIZEWINNER: "Prizewinner",
            CompetitionLevel.PRELIMINARY_CHAMPIONSHIP: "Prelim Champ",
            CompetitionLevel.OPEN_CHAMPIONSHIP: "Open Champ",
        }
        
        dance_names = {
            DanceType.REEL: "Reel",
            DanceType.LIGHT_JIG: "Light Jig",
            DanceType.SLIP_JIG: "Slip Jig",
            DanceType.TREBLE_JIG: "Treble Jig",
            DanceType.HORNPIPE: "Hornpipe",
            DanceType.TRADITIONAL_SET: "Trad Set",
            DanceType.CONTEMPORARY_SET: "Set Dance",
            DanceType.TREBLE_REEL: "Treble Reel",
        }
        
        gender_label = "Girls" if gender == Gender.FEMALE else "Boys"
        age_label = f"U{max_age+1}" if max_age < 99 else "Adult"
        
        if dance_type:
            dance_name = dance_names[dance_type]
            name = f"{level_names[level]} {age_label} {gender_label} {dance_name}"
        else:
            name = f"{level_names[level]} {age_label} {gender_label}"
        
        # Generate code
        code = generate_competition_code(
            level=level.value,
            min_age=min_age,
            dance_type=dance_type.value if dance_type else None,
            gender=gender.value if gender else None
        )
        
        # Assign to a stage based on level
        if level in [CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP]:
            stage = stages[0] if stages else None  # Main stage for champs
        elif level in [CompetitionLevel.BEGINNER_1, CompetitionLevel.BEGINNER_2]:
            stage = stages[-1] if len(stages) > 1 else stages[0]  # Last stage for beginners
        else:
            stage = random.choice(stages) if stages else None
        
        comp = Competition(
            id=uuid4(),
            feis_id=feis.id,
            name=name,
            min_age=min_age,
            max_age=max_age,
            level=level,
            gender=gender,
            code=code,
            dance_type=dance_type,
            tempo_bpm=get_default_tempo(dance_type) if dance_type else None,
            bars=48 if level not in [CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP] else 64,
            scoring_method=scoring_method,
            price_cents=1200 if scoring_method == ScoringMethod.SOLO else 4500,
            stage_id=stage.id if stage else None,
        )
        self.session.add(comp)
        return comp
    
    def _create_dancer_with_entries(
        self,
        parent: User,
        feis: Feis,
        competitions: List[Competition],
        dancer_index: int
    ) -> Tuple[Dancer, List[Entry]]:
        """Create a dancer and register them for competitions."""
        # Random attributes
        gender = random.choice([Gender.FEMALE, Gender.MALE])
        # Weight towards females (Irish dance has more girls)
        if random.random() < 0.75:
            gender = Gender.FEMALE
        
        comp_age = weighted_choice(AGE_WEIGHTS)
        level = weighted_choice(LEVEL_WEIGHTS)
        
        # Adjust level for very young dancers
        if comp_age <= 7:
            level = random.choice([CompetitionLevel.FIRST_FEIS, CompetitionLevel.BEGINNER_1, CompetitionLevel.BEGINNER_2])
        elif comp_age <= 9 and level in [CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP]:
            level = CompetitionLevel.PRIZEWINNER
        
        first, last = generate_dancer_name(gender)
        dob = random_date_of_birth(comp_age, feis.date)
        
        # Assign to a school
        school = random.choice(self.demo_teachers) if self.demo_teachers else None
        
        dancer = Dancer(
            id=uuid4(),
            parent_id=parent.id,
            school_id=school.id if school else None,
            name=f"{first} {last}",
            dob=dob,
            current_level=level,
            gender=gender
        )
        self.session.add(dancer)
        self.session.flush()
        self.demo_dancers.append(dancer)
        
        # Find eligible competitions
        eligible = [
            c for c in competitions
            if c.level == level
            and c.min_age <= comp_age <= c.max_age
            and (c.gender is None or c.gender == gender)
        ]
        
        # Register for competitions
        if level in [CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP]:
            # For champs, register for just the one main competition
            selected_comps = eligible
        else:
            # For grades, register for 2-5 individual dances
            num_entries = min(random.randint(2, 5), len(eligible))
            selected_comps = random.sample(eligible, num_entries) if eligible else []
        
        entries = []
        for comp in selected_comps:
            entry = Entry(
                id=uuid4(),
                dancer_id=dancer.id,
                competition_id=comp.id,
                paid=random.random() < 0.8,  # 80% paid
                pay_later=random.random() < 0.2,  # 20% pay at door
            )
            self.session.add(entry)
            entries.append(entry)
        
        self.session.flush()
        return dancer, entries
    
    def _assign_competitor_numbers(self, feis_id: UUID):
        """Assign competitor numbers to all entries in a feis."""
        entries = self.session.exec(
            select(Entry)
            .join(Competition)
            .where(Competition.feis_id == feis_id)
            .join(Dancer)
            .order_by(Dancer.name)
        ).all()
        
        # Group by dancer to give same number
        dancer_numbers = {}
        current_number = 101
        
        for entry in entries:
            if entry.dancer_id not in dancer_numbers:
                dancer_numbers[entry.dancer_id] = current_number
                current_number += 1
            entry.competitor_number = dancer_numbers[entry.dancer_id]
            self.session.add(entry)
        
        self.session.flush()
    
    def _create_schedule(self, feis: Feis, stages: List[Stage], competitions: List[Competition]):
        """Create a schedule for competitions across stages."""
        feis_datetime = datetime.combine(feis.date, datetime.min.time())
        start_time = feis_datetime + timedelta(hours=8)  # 8 AM start
        
        # Group competitions by stage
        by_stage = {s.id: [] for s in stages}
        unassigned = []
        
        for comp in competitions:
            if comp.stage_id and comp.stage_id in by_stage:
                by_stage[comp.stage_id].append(comp)
            else:
                unassigned.append(comp)
        
        # Distribute unassigned
        for i, comp in enumerate(unassigned):
            stage = stages[i % len(stages)]
            comp.stage_id = stage.id
            by_stage[stage.id].append(comp)
        
        # Schedule each stage
        for stage_id, stage_comps in by_stage.items():
            current_time = start_time
            
            # Sort by level then age for logical flow
            stage_comps.sort(key=lambda c: (
                list(CompetitionLevel).index(c.level),
                c.min_age
            ))
            
            for comp in stage_comps:
                # Count entries
                entry_count = self.session.exec(
                    select(Entry).where(Entry.competition_id == comp.id)
                ).all()
                
                duration = estimate_competition_duration(comp, len(entry_count))
                
                comp.scheduled_time = current_time
                comp.estimated_duration_minutes = duration
                self.session.add(comp)
                
                current_time += timedelta(minutes=duration + 5)  # 5 min buffer
        
        self.session.flush()
    
    def _generate_scores_for_feis(self, feis: Feis) -> int:
        """Generate realistic scores for all competitions in a feis."""
        score_count = 0
        
        competitions = self.session.exec(
            select(Competition).where(Competition.feis_id == feis.id)
        ).all()
        
        for comp in competitions:
            entries = self.session.exec(
                select(Entry).where(Entry.competition_id == comp.id)
            ).all()
            
            if not entries:
                continue
            
            # Determine number of judges
            if comp.scoring_method == ScoringMethod.CHAMPIONSHIP:
                num_judges = 3
            else:
                num_judges = 1
            
            # Select judges
            judges = self.demo_adjudicators[:num_judges] if self.demo_adjudicators else []
            if not judges:
                continue
            
            # Generate scores
            for judge in judges:
                # Generate raw scores with realistic distribution
                raw_scores = []
                for entry in entries:
                    # Base score around 70-90, with variation
                    base = random.gauss(80, 8)
                    score = max(50, min(100, base))
                    raw_scores.append((entry, round(score, 1)))
                
                # Ensure no exact ties (judges avoid them)
                values_seen = set()
                for i, (entry, score) in enumerate(raw_scores):
                    while score in values_seen:
                        score += 0.1
                    values_seen.add(score)
                    raw_scores[i] = (entry, score)
                
                # Save scores
                for entry, score in raw_scores:
                    judge_score = JudgeScore(
                        id=uuid4(),  # UUID object, not string
                        judge_id=str(judge.id),
                        competitor_id=str(entry.id),
                        round_id=str(comp.id),
                        value=score,
                        timestamp=datetime.combine(feis.date, datetime.min.time()) + timedelta(hours=10)
                    )
                    self.session.add(judge_score)
                    score_count += 1
        
        self.session.flush()
        return score_count


# ============= Public API =============

def populate_demo_data(session: Session) -> dict:
    """
    Populate the database with demo data.
    
    Returns a summary of what was created.
    """
    generator = DemoDataGenerator(session)
    return generator.generate_all()


def delete_demo_data(session: Session) -> dict:
    """
    Delete all demo data from the database.
    
    Identifies demo data by email patterns (demo_*@openfeis.demo).
    
    Returns a summary of what was deleted.
    """
    summary = {
        "users_deleted": 0,
        "feiseanna_deleted": 0,
        "dancers_deleted": 0,
        "entries_deleted": 0,
        "scores_deleted": 0,
    }
    
    # Find demo users
    demo_users = session.exec(
        select(User).where(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    ).all()
    
    demo_user_ids = [u.id for u in demo_users]
    
    if not demo_user_ids:
        return summary
    
    # Delete feiseanna owned by demo organizer (cascades to competitions, entries, etc.)
    demo_feiseanna = session.exec(
        select(Feis).where(Feis.organizer_id.in_(demo_user_ids))
    ).all()
    
    for feis in demo_feiseanna:
        # Delete feis settings
        settings = session.exec(
            select(FeisSettings).where(FeisSettings.feis_id == feis.id)
        ).first()
        if settings:
            session.delete(settings)
        
        # Delete fee items
        fee_items = session.exec(
            select(FeeItem).where(FeeItem.feis_id == feis.id)
        ).all()
        for fi in fee_items:
            session.delete(fi)
        
        # Delete stages
        stages = session.exec(
            select(Stage).where(Stage.feis_id == feis.id)
        ).all()
        for stage in stages:
            # Delete stage judge coverage
            coverages = session.exec(
                select(StageJudgeCoverage).where(StageJudgeCoverage.stage_id == stage.id)
            ).all()
            for cov in coverages:
                session.delete(cov)
            session.delete(stage)
        
        # Delete competitions and their entries/scores
        competitions = session.exec(
            select(Competition).where(Competition.feis_id == feis.id)
        ).all()
        
        for comp in competitions:
            # Delete scores
            scores = session.exec(
                select(JudgeScore).where(JudgeScore.round_id == str(comp.id))
            ).all()
            for score in scores:
                session.delete(score)
                summary["scores_deleted"] += 1
            
            # Delete entries
            entries = session.exec(
                select(Entry).where(Entry.competition_id == comp.id)
            ).all()
            for entry in entries:
                session.delete(entry)
                summary["entries_deleted"] += 1
            
            session.delete(comp)
        
        # Delete feis adjudicators
        feis_adjudicators = session.exec(
            select(FeisAdjudicator).where(FeisAdjudicator.feis_id == feis.id)
        ).all()
        for fa in feis_adjudicators:
            # Delete stage coverage linked to this adjudicator
            coverages = session.exec(
                select(StageJudgeCoverage).where(StageJudgeCoverage.feis_adjudicator_id == fa.id)
            ).all()
            for cov in coverages:
                session.delete(cov)
            
            session.delete(fa)

        session.delete(feis)
        summary["feiseanna_deleted"] += 1
    
    # Delete dancers owned by demo parents
    demo_dancers = session.exec(
        select(Dancer).where(Dancer.parent_id.in_(demo_user_ids))
    ).all()
    
    for dancer in demo_dancers:
        # Delete any remaining entries
        entries = session.exec(
            select(Entry).where(Entry.dancer_id == dancer.id)
        ).all()
        for entry in entries:
            session.delete(entry)
        
        # Delete placement history
        placements = session.exec(
            select(PlacementHistory).where(PlacementHistory.dancer_id == dancer.id)
        ).all()
        for p in placements:
            session.delete(p)
        
        session.delete(dancer)
        summary["dancers_deleted"] += 1
    
    # Delete demo users
    for user in demo_users:
        session.delete(user)
        summary["users_deleted"] += 1
    
    session.commit()
    
    return summary


def has_demo_data(session: Session) -> bool:
    """Check if demo data exists in the database."""
    demo_user = session.exec(
        select(User).where(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    ).first()
    return demo_user is not None
