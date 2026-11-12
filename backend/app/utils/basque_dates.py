import re
from datetime import date

MONTHS = "URTARRILA OTSAILA MARTXOA APIRILA MAIATZA EKAINA UZTAILA ABUZTUA IRAILA URRIA AZAROA ABENDUA".split()


def parse(value: str, year: int) -> date:
    match = re.fullmatch(r"([A-Z]+)K\s+(\d{1,2})", value.strip().upper())
    if not match:
        raise ValueError("Unrecognized Basque date")
    return date(year, MONTHS.index(match[1]) + 1, int(match[2]))


def format_date(value: date) -> str:
    return f"{MONTHS[value.month - 1]}K {value.day}"
