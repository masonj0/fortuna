# python_service/utils/text.py
# Centralized text and name normalization utilities
import re
from typing import Optional


def clean_text(text: Optional[str]) -> Optional[str]:
    """Strips leading/trailing whitespace and collapses internal whitespace."""
    if not text:
        return None
    return " ".join(text.strip().split())


def normalize_venue_name(name: Optional[str]) -> str:
    """
    Normalizes a racecourse name to a standard format.
    Aggressively strips race names, sponsorships, and country noise.
    """
    if not name:
        return "Unknown"

    # 1. Initial Cleaning: Replace dashes and strip all parenthetical info
    name = str(name).replace("-", " ")
    name = re.sub(r"\(.*?\)", " ", name)

    cleaned = clean_text(name)
    if not cleaned:
        return "Unknown"

    # 2. Aggressive Race/Meeting Name Stripping
    # If these keywords are found, assume everything after is the race name.
    RACING_KEYWORDS = [
        "PRIX", "CHASE", "HURDLE", "HANDICAP", "STAKES", "CUP", "LISTED", "GBB",
        "RACE", "MEETING", "NOVICE", "TRIAL", "PLATE", "TROPHY", "CHAMPIONSHIP",
        "JOCKEY", "TRAINER", "BEST ODDS", "GUARANTEED", "PRO/AM", "AUCTION",
        "HUNT", "MARES", "FILLIES", "COLTS", "GELDINGS", "JUVENILE", "SELLING",
        "CLAIMING", "OPTIONAL", "ALLOWANCE", "MAIDEN", "OPEN", "INVITATIONAL",
        "CLASS ", "GRADE ", "GROUP ", "DERBY", "OAKS", "GUINEAS", "ELIE DE",
        "FREDERIK", "CONNOLLY'S", "QUINNBET", "RED MILLS", "IRISH EBF", "SKY BET",
        "CORAL", "BETFRED", "WILLIAM HILL", "UNIBET", "PADDY POWER", "BETFAIR",
        "GET THE BEST", "CHELTENHAM TRIALS"
    ]

    upper_name = cleaned.upper()
    earliest_idx = len(cleaned)
    for kw in RACING_KEYWORDS:
        idx = upper_name.find(" " + kw)
        if idx != -1:
            earliest_idx = min(earliest_idx, idx)

    track_part = cleaned[:earliest_idx].strip()
    if not track_part:
        track_part = cleaned

    upper_track = track_part.upper()

    # 3. High-Confidence Mapping
    # Map raw/cleaned names to canonical display names.
    VENUE_MAP = {
        "AQUEDUCT": "Aqueduct",
        "ASCOT": "Ascot",
        "AYR": "Ayr",
        "BANGOR ON DEE": "Bangor-on-Dee",
        "CATTERICK": "Catterick",
        "CATTERICK BRIDGE": "Catterick",
        "CENTRAL PARK": "Central Park",
        "CHELMSFORD": "Chelmsford",
        "CHELMSFORD CITY": "Chelmsford",
        "CURRAGH": "Curragh",
        "DELTA DOWNS": "Delta Downs",
        "DONCASTER": "Doncaster",
        "DOWN ROYAL": "Down Royal",
        "DUNDALK": "Dundalk",
        "DUNSTALL PARK": "Wolverhampton",
        "EPSOM": "Epsom",
        "EPSOM DOWNS": "Epsom",
        "FAIR GROUNDS": "Fair Grounds",
        "FONTWELL": "Fontwell Park",
        "FONTWELL PARK": "Fontwell Park",
        "GREAT YARMOUTH": "Great Yarmouth",
        "GULFSTREAM": "Gulfstream Park",
        "GULFSTREAM PARK": "Gulfstream Park",
        "HAYDOCK": "Haydock Park",
        "HAYDOCK PARK": "Haydock Park",
        "HOVE": "Hove",
        "KEMPTON": "Kempton Park",
        "KEMPTON PARK": "Kempton Park",
        "LAUREL PARK": "Laurel Park",
        "LINGFIELD": "Lingfield Park",
        "LINGFIELD PARK": "Lingfield Park",
        "LOS ALAMITOS": "Los Alamitos",
        "MARONAS": "Maronas",
        "MUSSELBURGH": "Musselburgh",
        "NAAS": "Naas",
        "NEWCASTLE": "Newcastle",
        "NEWMARKET": "Newmarket",
        "OXFORD": "Oxford",
        "PAU": "Pau",
        "SAM HOUSTON": "Sam Houston",
        "SAM HOUSTON RACE PARK": "Sam Houston",
        "SANDOWN": "Sandown Park",
        "SANDOWN PARK": "Sandown Park",
        "SANTA ANITA": "Santa Anita",
        "SHEFFIELD": "Sheffield",
        "STRATFORD": "Stratford-on-Avon",
        "SUNLAND PARK": "Sunland Park",
        "TAMPA BAY DOWNS": "Tampa Bay Downs",
        "THURLES": "Thurles",
        "TURF PARADISE": "Turf Paradise",
        "UTTOXETER": "Uttoxeter",
        "VINCENNES": "Vincennes",
        "WARWICK": "Warwick",
        "WETHERBY": "Wetherby",
        "WOLVERHAMPTON": "Wolverhampton",
        "YARMOUTH": "Great Yarmouth",
    }

    # Direct match
    if upper_track in VENUE_MAP:
        return VENUE_MAP[upper_track]

    # Prefix match (sort by length desc to avoid partial matches on shorter names)
    for known_track in sorted(VENUE_MAP.keys(), key=len, reverse=True):
        if upper_name.startswith(known_track):
            return VENUE_MAP[known_track]

    return track_part.title()


def get_canonical_venue(name: Optional[str]) -> str:
    """Returns a sanitized canonical form for deduplication keys."""
    if not name:
        return "unknown"
    # Remove everything in parentheses
    name = re.sub(r"\(.*?\)", "", str(name))
    # Remove special characters, lowercase, strip
    name = re.sub(r"[^a-z0-9]", "", name.lower())
    return name or "unknown"


def normalize_course_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name
