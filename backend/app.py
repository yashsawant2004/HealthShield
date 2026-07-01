"""
app.py
------
Flask backend exposing the recommendation API consumed by the frontend.
The frontend calls /api/recommend on every input change (debounced) so
results update live as the user fills the form. Also exposes top-up
recommendations (for renewal users), a profile-independent top-10
overall list, and on-demand PDF brochure generation per policy.
"""

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from recommender import recommend, recommend_topup, top_overall, get_filter_options, POLICIES
from brochure import generate_brochure

import os
import json

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
BROCHURE_MAP_PATH = os.path.join(os.path.dirname(__file__), "brochure_map.json")

# Any file in real_brochures/ smaller than this is treated as a placeholder/
# stub rather than a genuine insurer brochure, and gets skipped in favour of
# the auto-generated informative PDF. A real scanned/typeset brochure (even a
# short one) is essentially always well above this size; a stub text file is
# a few hundred bytes to a couple of KB.
MIN_REAL_BROCHURE_BYTES = 20 * 1024  # 20 KB

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


def load_brochure_map():
    """Maps policy_id (str) -> relative path of a real uploaded brochure PDF.
    Built/refreshed by running build_brochure_map.py. Missing/empty file is
    fine - every policy then just falls back to the auto-generated PDF."""
    if not os.path.exists(BROCHURE_MAP_PATH):
        return {}
    with open(BROCHURE_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


BROCHURE_MAP = load_brochure_map()


def is_genuine_brochure(path):
    """Reject placeholder/stub PDFs (near-empty files dropped in as a
    stand-in) so we never serve an uninformative 'brochure' to the user."""
    try:
        return os.path.getsize(path) >= MIN_REAL_BROCHURE_BYTES
    except OSError:
        return False


def get_real_brochure_path(policy_id):
    rel = BROCHURE_MAP.get(str(policy_id))
    if not rel:
        return None
    full_path = os.path.join(os.path.dirname(__file__), rel)
    if not os.path.exists(full_path) or not is_genuine_brochure(full_path):
        return None
    return full_path


def build_profile(payload):
    return {
        "age": float(payload.get("age") or 30),
        "gender": payload.get("gender", ""),
        "marital_status": payload.get("marital_status", ""),
        "occupation": payload.get("occupation", ""),
        "city_tier": payload.get("city_tier", ""),
        "state": payload.get("state", ""),
        "family_floater": bool(payload.get("family_floater", False)),
        "family_size": int(payload.get("family_size") or 1),
        "pre_existing_disease": bool(payload.get("pre_existing_disease", False)),
        "existing_conditions": payload.get("existing_conditions") or [],
        "smoker": bool(payload.get("smoker", False)),
        "alcohol": bool(payload.get("alcohol", False)),
        "bmi": float(payload.get("bmi") or 0) or None,
        "sum_insured": float(payload.get("sum_insured") or 0) or None,
        "budget": float(payload.get("budget") or 0) or None,
        "room_rent_preference": payload.get("room_rent_preference", ""),
        "premium_frequency_preference": payload.get("premium_frequency_preference", ""),
        "is_renewal": bool(payload.get("is_renewal", False)),
        "current_insurer": payload.get("current_insurer", ""),
        "current_sum_insured": float(payload.get("current_sum_insured") or 0) or None,
        "requirements": payload.get("requirements") or [],
        "other_requirement": payload.get("other_requirement", ""),
    }


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/meta", methods=["GET"])
def meta():
    return jsonify(get_filter_options())


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    payload = request.get_json(force=True, silent=True) or {}
    profile = build_profile(payload)
    top_n = int(payload.get("top_n") or 5)
    results = recommend(profile, top_n=top_n)
    return jsonify({
        "count": len(results),
        "profile_used": profile,
        "recommendations": results,
    })


@app.route("/api/topup", methods=["POST"])
def api_topup():
    """Top-up / super top-up suggestions - primarily intended for
    renewal users who already have a base policy."""
    payload = request.get_json(force=True, silent=True) or {}
    profile = build_profile(payload)
    top_n = int(payload.get("top_n") or 5)
    results = recommend_topup(profile, top_n=top_n)
    return jsonify({
        "count": len(results),
        "is_renewal": profile["is_renewal"],
        "recommendations": results,
    })


@app.route("/api/catalog", methods=["GET"])
def api_catalog():
    """All policies grouped by insurance company for the Home page."""
    groups = {}
    for p in POLICIES:
        c = p["insurance_company"]
        if c not in groups:
            groups[c] = []
        groups[c].append({
            "id": p["id"],
            "policy_name": p["policy_name"],
            "policy_variant": p.get("policy_variant", ""),
            "policy_type": p.get("policy_type", ""),
            "sum_insured_raw": p.get("sum_insured_raw", ""),
            "rating": p.get("rating", 3.5),
            "is_family_floater": p.get("is_family_floater", False),
            "is_top_up": p.get("is_top_up", False),
            "maternity_cover": p.get("maternity_cover", "unknown"),
            "opd_cover": p.get("opd_cover", "unknown"),
            "best_for": p.get("best_for", ""),
        })
    return jsonify({"companies": groups, "total": len(POLICIES)})


@app.route("/api/top10", methods=["GET"])
def api_top10():
    """Profile-independent best-of-catalog list."""
    results = top_overall(top_n=10)
    return jsonify({"count": len(results), "recommendations": results})


@app.route("/api/brochure/<int:policy_id>", methods=["GET"])
def api_brochure(policy_id):
    policy = next((p for p in POLICIES if p["id"] == policy_id), None)
    if not policy:
        return jsonify({"error": "Policy not found"}), 404

    real_path = get_real_brochure_path(policy_id)
    if real_path and os.path.exists(real_path):
        path = real_path
    else:
        path = generate_brochure(policy)

    filename = f"{policy['insurance_company']}_{policy['policy_name']}.pdf".replace(" ", "_")
    return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
