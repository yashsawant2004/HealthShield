"""
data_processor.py
------------------
Reads the raw, free-text master_policies.xlsx sheet and converts it into a
clean, structured JSON file (data/policies_clean.json) that the recommender
engine can score quickly at request time.

The source sheet is human-curated and very inconsistent in formatting
(different units, ranges written as text, "Yes (with conditions)" style
flags, etc). Instead of trying to perfectly parse every cell, we use
best-effort regex extraction with safe fallbacks so the pipeline never
crashes on a weird row - it just falls back to a neutral/unknown value.
"""

import json
import re
import os
import openpyxl

RAW_XLSX = os.path.join(os.path.dirname(__file__), "master_policies.xlsx")
OUT_JSON = os.path.join(os.path.dirname(__file__), "..", "data", "policies_clean.json")

LAKH = 100_000
CRORE = 10_000_000


def to_text(v):
    return "" if v is None else str(v)


def first_number(text):
    """Return first number found in text (handles commas)."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def parse_money(token, default=None):
    """Parse a single rupee-ish token like '₹50 lac', '1 Crore', '7,000,000'."""
    if not token:
        return default
    t = token.lower().replace("₹", "").replace("rs.", "").replace("inr", "").strip()
    n = first_number(t)
    if n is None:
        return default
    if "crore" in t or "cr" in t:
        return n * CRORE
    if "lac" in t or "lakh" in t or re.search(r"\bl\b", t):
        return n * LAKH
    return n


def parse_premium(text):
    """Premiums in this sheet are example rupee figures (e.g. '₹5,426'),
    never lac/crore - so just grab the first plain rupee number."""
    text = to_text(text)
    if not text.strip():
        return None
    m = re.search(r"₹\s?([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_sum_insured_range(text):
    """Extract (min, max) sum insured in rupees from a messy text blob."""
    text = to_text(text)
    if not text.strip():
        return (None, None)
    # grab every money-like token e.g. ₹3 lac, 1 Crore, 7,000,000, 50L
    tokens = re.findall(r"₹?\s?[\d,]+(?:\.\d+)?\s?(?:lac|lakh|crore|cr|l\b)?", text, re.I)
    values = []
    for tok in tokens:
        v = parse_money(tok)
        if v and v >= 10000:  # ignore noise like stray small numbers
            values.append(v)
    if not values:
        return (None, None)
    return (min(values), max(values))


def parse_age_value(text):
    text = to_text(text)
    if not text.strip():
        return None
    low = text.lower()
    if "day" in low:  # e.g. "91 days" -> effectively 0 years for adult logic
        return 0
    n = first_number(text)
    return n


def parse_max_age(text):
    text = to_text(text)
    low = text.lower()
    if not text.strip() or "lifetime" in low or "lifelong" in low or "no age bar" in low or "no capping" in low:
        return 100
    n = first_number(text)
    return n if n else 100


def yesno(text):
    """Best effort Yes/No/Unknown flag."""
    text = to_text(text).strip().lower()
    if not text:
        return "unknown"
    if text.startswith("yes") or text.startswith("y "):
        return "yes"
    if text.startswith("no") or text == "n/a" or "not covered" in text or "no (" in text:
        return "no"
    if "yes" in text[:30]:
        return "yes"
    return "unknown"


def parse_rating(*texts):
    """Search across multiple columns (since some rows have shifted data)
    for a rating pattern like '4.5/5' or star symbols."""
    for t in texts:
        t = to_text(t)
        m = re.search(r"(\d(?:\.\d)?)\s*/\s*5", t)
        if m:
            return float(m.group(1))
        stars = t.count("★")
        if stars:
            return float(stars)
    return None


def parse_copay_deductible(text):
    text = to_text(text).strip().lower()
    if not text or text in ("none", "n/a", "no"):
        return "no"
    return "yes"


def row_to_policy(row, idx):
    (insurance_company, policy_name, policy_variant, policy_type, premium,
     premium_frequency, sum_insured, minimum_age, maximum_age,
     ped_wait, disease_wait, co_pay, deductible, restoration_benefit,
     super_reload, no_claim_bonus, opd_cover, maternity_cover,
     critical_illness_cover, accident_cover, room_rent_limit,
     cashless_hospital_count, claim_settlement_ratio, renewal_age,
     pre_hosp_days, post_hosp_days, ambulance_cover, daycare_treatments,
     ayush_cover, mental_illness_cover, modern_treatment_cover,
     organ_donor_cover, domiciliary_treatment, international_cover,
     annual_health_checkup, chronic_care_cover, policy_status,
     policy_rating, best_for, *_rest) = row

    if not insurance_company and not policy_name:
        return None

    min_si, max_si = parse_sum_insured_range(sum_insured)
    rating = parse_rating(policy_rating, policy_status, claim_settlement_ratio)

    policy = {
        "id": idx,
        "insurance_company": to_text(insurance_company).strip(),
        "policy_name": to_text(policy_name).strip(),
        "policy_variant": to_text(policy_variant).strip(),
        "policy_type": to_text(policy_type).strip(),
        "premium_raw": to_text(premium).strip(),
        "premium_value": parse_premium(premium),
        "premium_frequency": to_text(premium_frequency).strip(),
        "sum_insured_raw": to_text(sum_insured).strip(),
        "min_sum_insured": min_si,
        "max_sum_insured": max_si,
        "min_age": parse_age_value(minimum_age) or 0,
        "max_age": parse_max_age(maximum_age),
        "ped_waiting_period_raw": to_text(ped_wait).strip(),
        "co_pay": parse_copay_deductible(co_pay),
        "deductible": parse_copay_deductible(deductible),
        "restoration_benefit": yesno(restoration_benefit),
        "no_claim_bonus": yesno(no_claim_bonus),
        "opd_cover": yesno(opd_cover),
        "maternity_cover": yesno(maternity_cover),
        "critical_illness_cover": yesno(critical_illness_cover),
        "accident_cover": yesno(accident_cover),
        "room_rent_limit_raw": to_text(room_rent_limit).strip(),
        "cashless_hospital_count_raw": to_text(cashless_hospital_count).strip(),
        "ambulance_cover": yesno(ambulance_cover),
        "daycare_treatments": yesno(daycare_treatments),
        "ayush_cover": yesno(ayush_cover),
        "mental_illness_cover": yesno(mental_illness_cover),
        "organ_donor_cover": yesno(organ_donor_cover),
        "domiciliary_treatment": yesno(domiciliary_treatment),
        "international_cover": yesno(international_cover),
        "annual_health_checkup": yesno(annual_health_checkup),
        "chronic_care_cover": yesno(chronic_care_cover),
        "renewal_age_raw": to_text(renewal_age).strip(),
        "rating": rating if rating else 3.5,
        "best_for": to_text(best_for).strip() or to_text(policy_rating).strip(),
        "is_family_floater": "floater" in to_text(policy_type).lower(),
        "is_senior_citizen": "senior" in to_text(policy_type).lower(),
        "is_top_up": "top-up" in to_text(policy_type).lower() or "top up" in to_text(policy_type).lower(),
    }
    return policy


def main():
    wb = openpyxl.load_workbook(RAW_XLSX, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))[1:]  # skip header

    policies = []
    for i, row in enumerate(rows):
        p = row_to_policy(row, i + 1)
        if p:
            policies.append(p)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(policies, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(policies)} policies -> {OUT_JSON}")


if __name__ == "__main__":
    main()
