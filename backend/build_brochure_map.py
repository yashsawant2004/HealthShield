"""
build_brochure_map.py
----------------------
Run this after you drop your real brochure PDFs into backend/real_brochures/.

It fuzzy-matches each PDF filename against (insurance_company + policy_name
+ policy_variant) for every policy in data/policies_clean.json, and writes
backend/brochure_map.json mapping:

    { "<policy_id>": "real_brochures/<filename>.pdf" }

This is a BEST-EFFORT match - always review the printed report and fix any
wrong/missing mappings by hand-editing brochure_map.json afterwards (just
change the filename value, or set it to null to fall back to the
auto-generated summary brochure for that policy).

Usage:
    python3 build_brochure_map.py
"""

import json
import os
import re
from difflib import SequenceMatcher

BASE = os.path.dirname(__file__)
REAL_DIR = os.path.join(BASE, "real_brochures")
DATA_PATH = os.path.join(BASE, "..", "data", "policies_clean.json")
MAP_PATH = os.path.join(BASE, "brochure_map.json")

# Skip placeholder/stub files (e.g. a one-line text file saved as .pdf) so
# they never get mapped as a policy's "real" brochure. A genuine insurer
# brochure PDF is always well above this size.
MIN_REAL_BROCHURE_BYTES = 20 * 1024  # 20 KB


def norm(s):
    s = s.lower()
    s = re.sub(r"\.pdf$", "", s)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def main():
    if not os.path.isdir(REAL_DIR):
        print(f"Folder not found: {REAL_DIR}")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        policies = json.load(f)

    all_pdfs = [f for f in os.listdir(REAL_DIR) if f.lower().endswith(".pdf")]
    if not all_pdfs:
        print(f"No PDF files found in {REAL_DIR}. Drop your brochures there first.")
        return

    files = []
    skipped_stubs = []
    for fname in all_pdfs:
        size = os.path.getsize(os.path.join(REAL_DIR, fname))
        if size < MIN_REAL_BROCHURE_BYTES:
            skipped_stubs.append((fname, size))
        else:
            files.append(fname)

    if skipped_stubs:
        print(f"Skipping {len(skipped_stubs)} file(s) that look like placeholder stubs, not real brochures:")
        for fname, size in skipped_stubs:
            print(f"  - {fname} ({size} bytes) -- too small to be a genuine brochure")
        print()

    if not files:
        print("No genuine (non-stub) brochure PDFs found. All policies will use the auto-generated brochure.")
        # fall through so we still (re)write brochure_map.json below, with
        # every entry null - this keeps the map file in sync with reality
        # instead of leaving a stale/missing map on disk.

    # load existing map if present, so re-runs don't clobber manual fixes
    existing = {}
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    mapping = dict(existing)
    report = []

    for policy in policies:
        pid = str(policy["id"])
        if pid in existing and existing[pid]:
            continue  # already mapped (manually or in a previous run)

        target = norm(f"{policy['insurance_company']} {policy['policy_name']} {policy.get('policy_variant','')}")

        best_file, best_score = None, 0.0
        for fname in files:
            score = similarity(target, norm(fname))
            if score > best_score:
                best_file, best_score = fname, score

        if best_file and best_score >= 0.45:
            mapping[pid] = f"real_brochures/{best_file}"
            report.append((policy["policy_name"], best_file, round(best_score, 2)))
        else:
            mapping[pid] = None  # no confident match -> falls back to generated PDF

    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"Wrote {MAP_PATH}")
    print(f"\nMatched {sum(1 for v in mapping.values() if v)} / {len(policies)} policies.\n")
    print("Review these matches (policy -> file, confidence):")
    for name, fname, score in sorted(report, key=lambda r: r[2]):
        flag = "  <-- LOW CONFIDENCE, check this" if score < 0.65 else ""
        print(f"  {score:.2f}  {name!r} -> {fname}{flag}")

    unmatched = [p["policy_name"] for p in policies if mapping.get(str(p["id"])) is None]
    if unmatched:
        print(f"\n{len(unmatched)} policies have NO match (will show the auto-generated brochure):")
        for n in unmatched:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
