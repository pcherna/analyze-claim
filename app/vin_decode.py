"""Local VIN decoding: model year (position 10) and make (WMI prefix).

Pure stdlib module. Callers are expected to pass VINs that already passed
basic validation (17 chars, valid charset), but every function guards
defensively.
"""

from datetime import datetime

# Position 10 (index 9) model-year codes, base cycle 1980-2009. The code
# repeats every 30 years. I, O, Q are invalid VIN-wide; U, Z, 0 are
# additionally invalid at position 10 — all are simply absent from the table.
_YEAR_CODES: dict[str, int] = {
    "A": 1980, "B": 1981, "C": 1982, "D": 1983, "E": 1984, "F": 1985,
    "G": 1986, "H": 1987, "J": 1988, "K": 1989, "L": 1990, "M": 1991,
    "N": 1992, "P": 1993, "R": 1994, "S": 1995, "T": 1996, "V": 1997,
    "W": 1998, "X": 1999, "Y": 2000,
    "1": 2001, "2": 2002, "3": 2003, "4": 2004, "5": 2005,
    "6": 2006, "7": 2007, "8": 2008, "9": 2009,
}
_YEAR_CYCLE = 30

# WMI prefix -> make, for the top 10 North American makes by US sales.
# Longest-prefix match (5 down to 2 chars); an explicit None marks a prefix
# that is recognized but ambiguous or out of scope — it stops fallthrough to
# shorter entries and defers the judgment to the LLM. Extend by adding rows.
WMI_MAKES: dict[str, str | None] = {
    # Ford (no bare "1F" — 1FU/1FV are Freightliner)
    "1FA": "Ford", "1FB": "Ford", "1FC": "Ford", "1FD": "Ford",
    "1FM": "Ford", "1FT": "Ford",                       # US cars / SUVs / trucks
    "2FA": "Ford", "2FM": "Ford", "2FT": "Ford",        # Canada
    "3FA": "Ford", "3FE": "Ford",                       # Mexico
    # Chevrolet (GM WMIs must stay 3-char: 1GT/1GK=GMC, 1GY/1G6=Cadillac, 1G4=Buick)
    "1G1": "Chevrolet", "2G1": "Chevrolet", "3G1": "Chevrolet",  # cars US/CA/MX
    "1GC": "Chevrolet", "1GB": "Chevrolet",                      # trucks / chassis
    "1GN": "Chevrolet",                                          # SUVs
    "3GC": "Chevrolet", "3GN": "Chevrolet",                      # Mexico trucks / SUVs
    "KL1": "Chevrolet", "KL8": "Chevrolet",                      # Korea-built (Spark/Aveo)
    # Toyota — 2-char fallback plus explicit Lexus carve-outs
    "JT": "Toyota",
    "JTH": None, "JTJ": None,                           # Lexus — defer to LLM
    "4T1": "Toyota", "4T3": "Toyota",                   # US cars
    "5TB": "Toyota", "5TD": "Toyota", "5TE": "Toyota", "5TF": "Toyota",  # US trucks/MPVs
    "2T1": "Toyota",                                    # Canada
    "3TM": "Toyota", "3TY": "Toyota",                   # Mexico (Tacoma)
    # Honda (no "JH" fallback — JH4 is Acura)
    "1HG": "Honda", "JHM": "Honda", "JHL": "Honda",
    "2HG": "Honda", "2HK": "Honda",                     # Canada
    "5FN": "Honda", "5FP": "Honda", "5J6": "Honda",     # US MPV/pickup/CR-V
    "19X": "Honda",                                     # US Civic
    # Nissan (excludes JNK/JNR/5N3 = Infiniti)
    "1N4": "Nissan", "1N6": "Nissan", "JN1": "Nissan", "JN8": "Nissan",
    "3N1": "Nissan", "3N6": "Nissan", "5N1": "Nissan",
    # Hyundai
    "KMH": "Hyundai", "KM8": "Hyundai", "5NP": "Hyundai", "5NM": "Hyundai",
    # Kia
    "KNA": "Kia", "KND": "Kia", "KNC": "Kia",
    "5XY": "Kia", "5XX": "Kia", "3KP": "Kia",
    # Jeep
    "1J4": "Jeep", "1J8": "Jeep",
    "1C4": None,  # Stellantis US SUVs: Jeep, but also Dodge Durango — defer to LLM
    # GMC
    "1GT": "GMC", "1GK": "GMC", "1GD": "GMC",
    "2GT": "GMC", "3GT": "GMC", "3GK": "GMC",
    # Ram (2011+; pre-2011 Dodge-branded trucks were 1D7, intentionally unmapped)
    "1C6": "Ram", "3C6": "Ram", "3C7": "Ram",
}


def decode_model_year(vin: str, *, now_year: int | None = None) -> int | None:
    """Best-guess model year from position 10: the most recent cycle candidate
    not later than next year. None if the position-10 code is invalid.

    Because the code repeats every 30 years this is a guess, suitable as an
    LLM hint; for the deterministic comparison use year_code_matches().
    """
    if len(vin) != 17:
        return None
    base = _YEAR_CODES.get(vin[9].upper())
    if base is None:
        return None
    limit = (now_year if now_year is not None else datetime.now().year) + 1
    while base + _YEAR_CYCLE <= limit:
        base += _YEAR_CYCLE
    return base


def year_code_matches(claimed_year: int, vin: str) -> bool | None:
    """Whether the claimed model year is consistent with VIN position 10,
    comparing modulo the 30-year cycle. None if the code is undecodable
    (no judgment possible).
    """
    if len(vin) != 17:
        return None
    base = _YEAR_CODES.get(vin[9].upper())
    if base is None:
        return None
    return (claimed_year - base) % _YEAR_CYCLE == 0


def decode_make(vin: str) -> str | None:
    """Make from the WMI via longest-prefix match, or None if unknown or
    deliberately ambiguous."""
    vin = vin.upper()
    for length in (5, 4, 3, 2):
        prefix = vin[:length]
        if prefix in WMI_MAKES:
            return WMI_MAKES[prefix]
    return None


def normalize_make(s: str) -> str:
    return s.strip().casefold()
