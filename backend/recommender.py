"""
recommender.py
---------------
Rule-based weighted-scoring recommendation engine.

Given a user profile (personal info + health info + requirements), every
policy in the catalog is scored 0-100. Hard constraints (age eligibility,
minimum sum insured) eliminate a policy outright. Everything else
(coverage preferences, budget, family floater need, pre-existing disease
friendliness, hospital network size, rating) contributes weighted points
to a soft score, so the ranking can shift smoothly as the user tweaks
inputs - which is what gives the "live" recommendation feel on the
frontend.
"""

import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "policies_clean.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    POLICIES = json.load(f)


def _yes(flag):
    return flag == "yes"


def passes_hard_filters(policy, profile):
    age = profile.get("age", 30)

    # Age eligibility (allow a little slack since text parsing is imperfect)
    if policy["min_age"] and age < policy["min_age"] - 1:
        return False
    if policy["max_age"] and age > policy["max_age"] + 1:
        return False

    # Family floater requirement
    if profile.get("family_floater") and not policy["is_family_floater"]:
        # don't hard-exclude individual plans entirely, they're still usable
        # per-member, but senior-only/top-up-only plans without floater are
        # less suitable -> handled in soft scoring instead of a hard cut
        pass

    # Required minimum sum insured - hard filter only if we actually
    # parsed a max_sum_insured for the policy (avoid rejecting due to
    # missing/unparsed data)
    required_si = profile.get("sum_insured")
    if required_si and policy["max_sum_insured"]:
        if policy["max_sum_insured"] < required_si * 0.5:
            return False

    return True


def score_policy(policy, profile):
    score = 0.0
    reasons = []

    # ---- Sum insured fit (25 pts) ----
    required_si = profile.get("sum_insured")
    if required_si and policy["max_sum_insured"]:
        if policy["max_sum_insured"] >= required_si:
            score += 25
            reasons.append("Covers your required sum insured")
        elif policy["max_sum_insured"] >= required_si * 0.75:
            score += 15
        else:
            score += 5
    else:
        score += 10  # unknown data, neutral credit

    # ---- Budget fit (15 pts) - only when we have a parsed premium ----
    budget = profile.get("budget")
    if budget and policy["premium_value"]:
        if policy["premium_value"] <= budget:
            score += 15
            reasons.append("Fits your budget")
        elif policy["premium_value"] <= budget * 1.25:
            score += 8
        else:
            score += 2
    else:
        score += 8  # unknown premium, neutral credit

    # ---- Family floater (8 pts) ----
    if profile.get("family_floater"):
        if policy["is_family_floater"]:
            score += 8
            reasons.append("Family floater plan")
        else:
            score += 2
    else:
        score += 5

    # ---- Pre-existing disease friendliness (8 pts) ----
    if profile.get("pre_existing_disease"):
        ped_text = policy["ped_waiting_period_raw"].lower()
        if "12 month" in ped_text or "1 year" in ped_text:
            score += 8
            reasons.append("Short pre-existing disease waiting period")
        elif "24 month" in ped_text or "2 year" in ped_text:
            score += 5
        elif "36 month" in ped_text or "3 year" in ped_text:
            score += 2
        else:
            score += 4
    else:
        score += 4

    # ---- Requirement flags (each worth up to 7 pts) ----
    requirement_map = {
        "maternity": ("maternity_cover", "Includes maternity cover"),
        "opd": ("opd_cover", "Includes OPD cover"),
        "critical_illness": ("critical_illness_cover", "Includes critical illness cover"),
        "accident": ("accident_cover", "Includes accident cover"),
        "ayush": ("ayush_cover", "Includes AYUSH / alternative treatment cover"),
        "mental_health": ("mental_illness_cover", "Includes mental health cover"),
        "international": ("international_cover", "Includes international treatment cover"),
        "annual_checkup": ("annual_health_checkup", "Free annual health checkup"),
        "chronic_care": ("chronic_care_cover", "Covers chronic disease management"),
        "no_claim_bonus": ("no_claim_bonus", "Offers no-claim bonus"),
        "restoration_benefit": ("restoration_benefit", "Sum insured restoration benefit"),
        "low_copay": ("co_pay", None),  # handled specially below
    }

    requirements = profile.get("requirements", [])
    for req in requirements:
        mapping = requirement_map.get(req)
        if not mapping:
            continue
        field, reason = mapping
        if req == "low_copay":
            if policy["co_pay"] == "no":
                score += 7
                reasons.append("No mandatory co-pay")
            else:
                score += 1
            continue
        if _yes(policy[field]):
            score += 7
            if reason:
                reasons.append(reason)
        else:
            score += 0.5

    # ---- "Others" free-text requirement (up to 6 pts) ----
    other_text = (profile.get("other_requirement") or "").strip().lower()
    if other_text:
        haystack = " ".join([
            policy.get("best_for", ""), policy.get("policy_name", ""),
            policy.get("policy_type", ""), policy.get("policy_variant", "")
        ]).lower()
        keywords = [w for w in other_text.replace(",", " ").split() if len(w) > 2]
        hits = sum(1 for w in keywords if w in haystack)
        if keywords and hits:
            score += min(6, hits * 2)
            reasons.append(f"Matches your note: \"{profile.get('other_requirement')}\"")

    # ---- Existing chronic conditions selected by user (up to 6 pts) ----
    conditions = profile.get("existing_conditions", [])
    if conditions:
        if _yes(policy["chronic_care_cover"]):
            score += 6
            reasons.append("Good for managing your existing condition(s)")
        else:
            score += 1

    # ---- BMI risk consideration (up to 3 pts, informational nudge) ----
    bmi = profile.get("bmi")
    if bmi and bmi >= 30:
        if policy["co_pay"] == "no" and _yes(policy["restoration_benefit"]):
            score += 3
            reasons.append("Favourable for higher-BMI applicants (no co-pay + restoration)")


    # ---- Senior citizen friendliness ----
    if profile.get("age", 30) >= 60:
        if policy["is_senior_citizen"] or policy["max_age"] >= 80:
            score += 6
            reasons.append("Senior-citizen friendly")

    # ---- Insurer/policy rating (10 pts) ----
    score += (policy["rating"] / 5.0) * 10
    if policy["rating"] >= 4.3:
        reasons.append(f"Highly rated ({policy['rating']}/5)")

    # ---- Hospital network size (5 pts) bonus when text mentions large count ----
    net = policy["cashless_hospital_count_raw"]
    if net and any(ch.isdigit() for ch in net):
        digits = "".join(ch for ch in net if ch.isdigit())
        if digits and int(digits) >= 5000:
            score += 5
            reasons.append("Large cashless hospital network")
        elif digits and int(digits) >= 1000:
            score += 3

    return round(min(score, 100), 1), reasons


def recommend(profile, top_n=5):
    """Return top_n policies ranked by fit score for the given user profile."""
    scored = []
    for policy in POLICIES:
        if not passes_hard_filters(policy, profile):
            continue
        score, reasons = score_policy(policy, profile)
        item = dict(policy)
        item["match_score"] = score
        item["match_reasons"] = reasons[:5]
        scored.append(item)

    scored.sort(key=lambda p: p["match_score"], reverse=True)
    return scored[:top_n]


def recommend_topup(profile, top_n=5):
    """Recommend top-up / super top-up policies - relevant for users who
    already hold a base health policy and want additional high-cost cover
    at a lower premium (deductible kicks in after base SI is exhausted)."""
    scored = []
    for policy in POLICIES:
        if not policy["is_top_up"]:
            continue
        if not passes_hard_filters(policy, profile):
            continue
        score, reasons = score_policy(policy, profile)
        item = dict(policy)
        item["match_score"] = score
        item["match_reasons"] = reasons[:5]
        scored.append(item)
    scored.sort(key=lambda p: p["match_score"], reverse=True)
    return scored[:top_n]


def top_overall(top_n=10):
    """A profile-independent 'best of catalog' list, ranked by disclosed
    rating (tie-broken by larger max sum insured and large hospital network)."""
    def net_size(p):
        digits = "".join(ch for ch in p["cashless_hospital_count_raw"] if ch.isdigit())
        return int(digits) if digits else 0

    ranked = sorted(
        POLICIES,
        key=lambda p: (p["rating"], p["max_sum_insured"] or 0, net_size(p)),
        reverse=True,
    )
    return ranked[:top_n]


def get_filter_options():
    companies = sorted({p["insurance_company"] for p in POLICIES if p["insurance_company"]})
    return {"insurance_companies": companies, "total_policies": len(POLICIES)}
