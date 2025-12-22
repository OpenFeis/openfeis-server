"""
Competition code generation following industry standards.

Format: [LevelDigit][AgeIndex][DanceCode][Variant?]

Examples:
- 407SJ = Novice (4), U7 (07), Slip Jig
- 609PC = Preliminary Championship (6), U9 (09)
- 515RL2 = Prizewinner (5), U15 (15), Reel, Second Chance
- 9210FD = Figure (9), U10 (10), 2-Hand

Level digits:
- 1 = First Feis
- 2 = Beginner 1
- 3 = Beginner 2 / Advanced Beginner  
- 4 = Novice
- 5 = Prizewinner / Open
- 6 = Preliminary Championship
- 7 = Open Championship
- 8-9 = Specials, teams, ceili, figure dances

Dance codes (Solo):
- RL = Reel
- LJ = Light Jig
- SJ = Slip Jig
- SN = Single Jig
- TJ = Treble Jig
- HP = Hornpipe
- TS = Traditional Set
- CS = Contemporary Set
- TR = Treble Reel
- PD = St. Patrick's Day

Figure/Ceili dance codes:
- 2H = 2-Hand
- 3H = 3-Hand
- 4H = 4-Hand
- 6H = 6-Hand
- 8H = 8-Hand

Championship round codes:
- PC = Preliminary Championship
- OC = Open Championship
"""

from typing import Optional

# Level to digit mapping
LEVEL_DIGITS = {
    "first_feis": "1",
    "beginner_1": "2",
    "beginner_2": "3",
    "novice": "4",
    "prizewinner": "5",
    "preliminary_championship": "6",
    "open_championship": "7",
}

# Dance type to code mapping
DANCE_CODES = {
    # Solo dances
    "REEL": "RL",
    "LIGHT_JIG": "LJ",
    "SLIP_JIG": "SJ",
    "SINGLE_JIG": "SN",
    "TREBLE_JIG": "TJ",
    "HORNPIPE": "HP",
    "TRADITIONAL_SET": "TS",
    "NON_TRADITIONAL_SET": "SD",
    "CONTEMPORARY_SET": "CS",
    "TREBLE_REEL": "TR",
    # Figure/Ceili dances
    "TWO_HAND": "2H",
    "THREE_HAND": "3H",
    "FOUR_HAND": "4H",
    "SIX_HAND": "6H",
    "EIGHT_HAND": "8H",
}

# Reverse mapping for display
DANCE_CODE_NAMES = {v: k for k, v in DANCE_CODES.items()}


def generate_competition_code(
    level: str,
    min_age: int,
    dance_type: Optional[str] = None,
    is_second_chance: bool = False,
    variant_suffix: Optional[str] = None,
    is_over: bool = False,
    is_mixed: bool = False,
    gender: Optional[str] = None
) -> str:
    """
    Generate a competition code following industry conventions.
    
    Args:
        level: Competition level (e.g., "novice", "preliminary_championship")
        min_age: Minimum age for the competition (used as age index)
        dance_type: Dance type enum value (e.g., "REEL", "SLIP_JIG")
        is_second_chance: Whether this is a second chance competition
        variant_suffix: Optional custom suffix (overrides second chance)
        is_over: Whether this is an "Over" age group (e.g. O15)
        is_mixed: Whether this is a mixed-gender competition (for Figure dances)
        gender: Optional gender ("male", "female", "other")
    
    Returns:
        Competition code string (e.g., "407SJ", "609PC", "9210FD", "9410FM")
    """
    # Get level digit
    level_digit = LEVEL_DIGITS.get(level.lower(), "9")
    
    # Age index - pad to 2 digits
    # Use min_age directly as the index (U6 -> 06, U10 -> 10, U15 -> 15)
    # For Over competitions, increment by 1 (O10 -> 11)
    target_age = min_age
    if is_over and min_age < 99:
        target_age += 1
        
    age_index = str(target_age).zfill(2)
    
    # For championships, use round code instead of dance code unless a specific set dance is requested
    if level.lower() in ("preliminary_championship", "open_championship") and dance_type not in ("TRADITIONAL_SET", "NON_TRADITIONAL_SET", "CONTEMPORARY_SET"):
        if level.lower() == "preliminary_championship":
            dance_code = "PC"
        else:
            dance_code = "OC"
    elif dance_type:
        dance_code = DANCE_CODES.get(dance_type.upper(), dance_type[:2].upper() if dance_type else "")
    else:
        dance_code = ""
    
    # Special logic for Figure/Ceili dances
    # Format: 9 + [Hands] + [Age] + [FD/FM]
    if dance_code in ["2H", "3H", "4H", "6H", "8H"]:
        first_digit = "9"
        hands_digit = dance_code[0]  # "2", "3", etc.
        
        # Age logic
        if min_age >= 99:
            # Adults
            age_str = "99"
        elif is_over:
            # Over 15 -> 16
            age_str = str(min_age + 1).zfill(2)
        else:
            # Under 10 -> 10
            age_str = str(min_age).zfill(2)
            
        suffix = "FM" if is_mixed else "FD"
        return f"{first_digit}{hands_digit}{age_str}{suffix}"

    # Build the code for solo/other
    code = f"{level_digit}{age_index}{dance_code}"
    
    # Add gender suffix for boys/males if not an open competition
    if gender == "male":
        code += "-M"
    
    # Add suffix
    if variant_suffix:
        code += variant_suffix
    elif is_second_chance:
        code += "2"
    
    return code


def parse_competition_code(code: str) -> dict:
    """
    Parse a competition code into its components.
    
    Args:
        code: Competition code string (e.g., "407SJ", "609PC2")
    
    Returns:
        Dictionary with level_digit, age_index, dance_code, suffix
    """
    if not code or len(code) < 3:
        return {}
    
    result = {
        "level_digit": code[0],
        "age_index": code[1:3] if len(code) >= 3 else "",
        "dance_code": "",
        "suffix": ""
    }
    
    # Extract dance code and suffix
    remaining = code[3:]
    if remaining:
        # Dance codes are typically 2 letters
        if len(remaining) >= 2 and remaining[:2].isalpha():
            result["dance_code"] = remaining[:2]
            result["suffix"] = remaining[2:]
        else:
            result["suffix"] = remaining
    
    return result


def get_level_name(level_digit: str) -> str:
    """Get human-readable level name from digit."""
    names = {
        "1": "First Feis",
        "2": "Beginner 1",
        "3": "Beginner 2",
        "4": "Novice",
        "5": "Prizewinner",
        "6": "Preliminary Championship",
        "7": "Open Championship",
        "8": "Special",
        "9": "Special",
    }
    return names.get(level_digit, "Unknown")


def get_dance_name(dance_code: str) -> str:
    """Get human-readable dance name from code."""
    names = {
        # Solo dances
        "RL": "Reel",
        "LJ": "Light Jig",
        "SJ": "Slip Jig",
        "SN": "Single Jig",
        "TJ": "Treble Jig",
        "HP": "Hornpipe",
        "TS": "Traditional Set",
        "SD": "Non-Traditional Set",
        "CS": "Contemporary Set",
        "TR": "Treble Reel",
        # Figure/Ceili dances
        "2H": "2-Hand",
        "3H": "3-Hand",
        "4H": "4-Hand",
        "6H": "6-Hand",
        "8H": "8-Hand",
        # Championships
        "PC": "Preliminary Championship",
        "OC": "Open Championship",
    }
    return names.get(dance_code.upper(), dance_code)

