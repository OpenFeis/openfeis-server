"""
Script to populate a specific feis with realistic registration data based on a screenshot.
"""

import random
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import uuid4, UUID
from sqlmodel import Session, select

from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Entry, Dancer, RoleType, Gender, 
    CheckInStatus, CompetitionLevel, DanceType
)
from backend.api.auth import hash_password

# Irish-flavored names for realism (copied from demo_data.py)
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

DEMO_PASSWORD = "demo123"
DEMO_EMAIL_DOMAIN = "atlanta.demo"

# Counts from the screenshot
SCREENSHOT_COUNTS = {
    # Stages 1/2
    "9216FD": 1, "9316FD": 1, "9499FD": 13, "9416FD": 30, "9416FM": 6, "9616FD": 17, "9818FD": 16, "9819FD": 1, "9819FM": 1,
    # Stages 3/4
    "9215FD": 6, "9210FD": 16, "9312FD": 3, "9410FD": 35, "9412FM": 24, "9610FD": 14, "9812FD": 7,
    "9315FD": 5, "9415FM": 26, "9615FD": 32, "9815FM": 16, "9299FD": 1, "9415FD": 43, "9815FD": 15,
    # Beginner / Adv Beginner (Stage 1/2)
    "310RLA": 9, "310RLB": 10, "308RL": 6, "309RL": 7, "311RL": 9, "307RL": 9, "208RL": 5, "207RL": 5, "210RL": 5, "211RL": 2, "299RL": 3, "499RL": 3, "399RL": 1,
    "310SJ": 13, "307SJ": 9, "208SJ": 2, "207SJ": 2, "299SJ": 1, "499SJ": 4, "399SJ": 1,
    "309SJ": 12, "311SJ": 7, "210SJ": 5, "399SJ": 1,
    "311LJB": 10, "311LJA": 10, "308LJ": 8, "309LJ": 6, "312LJ": 5, "307LJ": 6, "207LJ": 5, "306LJ": 5, "211LJ": 4, "210LJ": 5, "299LJ": 3, "399LJ": 1, "499LJ": 1,
    "310S": 10, "311S": 7, "309S": 6, "308S": 9, "306S": 5, "208S": 2, "210S": 3,
    # Shoe Change & Later Day
    "499TJ": 1, "299TJ": 1, "310TJA": 11, "308TJ": 8, "310TJB": 10, "311TJ": 8, "307HP": 5, "309HP": 11, "311HP": 10, "310HP": 11, "499HP": 1,
    "511TJ": 14, "509TJ": 8, "412TJ": 8, "411TJ": 8, "414TJ": 5, "409HP": 9, "410HP": 8, "513HP": 10, "514HP": 8, "512HP": 8, "509TS": 11, "513TS": 10, "514TR": 5,
    "513TJ": 16, "514TJ": 11, "408TJ": 8, "409TJ": 8, "410TJ": 8, "411HP": 10, "413HP": 9, "414HP": 8, "511HP": 11, "510HP": 8, "509HP": 8, "511TS": 14, "514TS": 11, "511TR": 5,
    "599TS": 11,
    # Novice / Prizewinner
    "512RL": 13, "513RL": 10, "510RL": 6, "514RL": 8, "509RL": 5, "516RL": 5, "413RL": 5, "508RL": 5, "412RL": 8, "414RL": 5, "410RL": 11, "409RL": 14, "411RL": 9, "408RL": 9, "407RL": 7,
    "513SJ": 12, "512SJ": 14, "514SJ": 9, "510SJ": 6, "414SJ": 6, "509SJ": 6, "409SJ": 13, "413SJ": 9, "411SJ": 9, "410SJ": 10, "408SJ": 5, "407SJ": 5,
    "409LJ": 9, "410LJ": 8, "408LJ": 9, "411LJ": 5, "412LJ": 5,
    "409S": 7, "411S": 7, "408S": 8, "410S": 5,
    # First Feis
    "107RL": 4, "109RL": 6, "105LJ": 5, "105RL": 4, "107LJ": 2, "109LJ": 6,
    # Championships
    "709OC": 3, "710OC": 4, "609PC": 11, "610PC": 8, "611PC": 7,
    "712OC": 3, "713OC": 6, "713OC-M": 7, "714OC": 12, "715OC-M": 6, "715OC": 15,
    "717OC": 8, "716OC": 12, "799OC": 5, "719OC": 6, "720OC": 4,
    "612PC": 11, "614PC": 14, "613PC": 10, "615PC": 10, "616PC": 14, "617PC": 12, "699PC": 8,
    "814TS": 6, "811TS": 13, "815TS": 5,
    # Sets/SD
    "510SD": 3, "512SD": 6, "514SD": 5, "516SD": 4, "617SD": 6, "614SD": 22,
    "610SD": 10, "616SD": 21, "612SD": 18
}

def generate_dancer_name(gender: Gender) -> Tuple[str, str]:
    if gender == Gender.FEMALE:
        first = random.choice(GIRL_FIRST_NAMES)
    else:
        first = random.choice(BOY_FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last

def random_date_of_birth(competition_age: int, feis_date: date) -> date:
    competition_year = feis_date.year
    birth_year = competition_year - competition_age
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    return date(birth_year, birth_month, birth_day)

def populate_atlanta_registrations(session: Session, feis_name: str):
    print(f"Starting population for '{feis_name}'...")
    
    # 1. Find feis
    feis = session.exec(select(Feis).where(Feis.name == feis_name)).first()
    if not feis:
        print(f"Feis '{feis_name}' not found.")
        return

    # 2. Get all competitions for this feis
    competitions = session.exec(select(Competition).where(Competition.feis_id == feis.id)).all()
    print(f"Found {len(competitions)} competitions in the feis.")

    # 3. Create a pool of parents
    parents = []
    for i in range(100):
        email = f"parent_{i}@{DEMO_EMAIL_DOMAIN}"
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            parents.append(existing)
            continue
        
        first, last = generate_dancer_name(Gender.FEMALE)
        parent = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            role=RoleType.PARENT,
            name=f"{first} {last}",
            email_verified=True
        )
        session.add(parent)
        parents.append(parent)
    session.flush()

    # 4. Map competitions by code
    code_to_comps = {}
    for comp in competitions:
        if comp.code:
            if comp.code not in code_to_comps:
                code_to_comps[comp.code] = []
            code_to_comps[comp.code].append(comp)

    # 5. Populate entries
    total_entries = 0
    dancer_counter = 0
    
    for code, target_count in SCREENSHOT_COUNTS.items():
        # Try exact match first, then prefix match
        matched_comps = code_to_comps.get(code, [])
        if not matched_comps:
            # Fuzzy mappings for common code variations
            fuzzy_code = code
            if fuzzy_code.endswith('S'): fuzzy_code = fuzzy_code[:-1] + 'SN'
            
            # Map U11/O10 codes if they don't exist
            if '311' in fuzzy_code: fuzzy_code = fuzzy_code.replace('311', '310')
            if '312' in fuzzy_code: fuzzy_code = fuzzy_code.replace('312', '311')
            
            matched_comps = code_to_comps.get(fuzzy_code, [])
            
            if not matched_comps:
                # Try prefix match (e.g. 310RLA -> matches 310RL)
                for c_code, c_comps in code_to_comps.items():
                    if code.startswith(c_code) or fuzzy_code.startswith(c_code):
                        matched_comps = c_comps
                        break
        
        if not matched_comps:
            print(f"Warning: Competition with code '{code}' not found in feis.")
            continue

        # If multiple comps match the same code (e.g. 310RL has U10 and O10)
        # and we have A/B suffix, try to be specific.
        if len(matched_comps) > 1:
            if code.endswith('A'):
                # Pick the younger one
                matched_comps = [min(matched_comps, key=lambda x: x.max_age)]
            elif code.endswith('B'):
                # Pick the older one
                matched_comps = [max(matched_comps, key=lambda x: x.max_age)]
            else:
                # If no suffix but multiple comps, split the count
                pass # We'll handle splitting below

        # Partition target count among matched comps
        per_comp_target = target_count // len(matched_comps)
        
        for comp in matched_comps:
            # Check existing entries
            existing_count = len(comp.entries)
            needed = per_comp_target - existing_count
            if needed <= 0:
                continue

            print(f"Populating {needed} entries for {code} ({comp.name})")
        
            for _ in range(needed):
                # Create a new dancer for this entry to ensure counts match exactly
                # In a real scenario, dancers enter multiple comps, but for populating 
                # to match a screenshot, this is simpler and more precise.
                dancer_counter += 1
                parent = random.choice(parents)
                
                # Determine gender from comp name/code if possible
                gender = Gender.FEMALE
                if "Boy" in comp.name or "Male" in comp.name:
                    gender = Gender.MALE
                elif comp.gender == Gender.MALE:
                    gender = Gender.MALE

                first, last = generate_dancer_name(gender)
                dob = random_date_of_birth(comp.max_age if comp.max_age < 90 else 25, feis.date)
                
                dancer = Dancer(
                    id=uuid4(),
                    parent_id=parent.id,
                    name=f"{first} {last}",
                    dob=dob,
                    current_level=comp.level,
                    gender=gender
                )
                session.add(dancer)
                session.flush()
                
                entry = Entry(
                    id=uuid4(),
                    dancer_id=dancer.id,
                    competition_id=comp.id,
                    paid=True,
                    check_in_status=CheckInStatus.NOT_CHECKED_IN
                )
                session.add(entry)
                total_entries += 1

    session.commit()
    print(f"Successfully added {total_entries} entries across competitions.")

if __name__ == "__main__":
    from backend.db.database import engine, create_db_and_tables
    # Ensure database is up to date with latest migrations
    create_db_and_tables()
    
    with Session(engine) as session:
        populate_atlanta_registrations(session, "Faux Atlanta Winter Feis")

