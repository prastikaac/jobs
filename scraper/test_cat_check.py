"""
test_cat_check.py — Quick test for the LM Studio category post-check.

Run from the project root:
    python scraper/test_cat_check.py

What it does:
  1. Checks if LM Studio is reachable on port 1234.
  2. Detects the currently loaded model.
  3. Runs a few category checks against fake jobs.
  4. Prints the result clearly.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))   # make scraper imports work

import category_post_check as cpc

# ── 1. Connectivity check ─────────────────────────────────────────────────────
print("\n-- LM Studio connectivity ----------------------------------------------")
resp = cpc._lmstudio_get("/v1/models")
if resp is None:
    print("X LM Studio is OFFLINE or not reachable on http://localhost:1234")
    print("  -> Open LM Studio -> Developer tab -> Start Server")
    sys.exit(1)

models = resp.get("data", [])
if not models:
    print("X LM Studio is running but NO model is loaded.")
    print("  -> Load a model from the LM Studio catalog first.")
    sys.exit(1)

model_id = models[0]["id"]
print(f"OK LM Studio is online.  Loaded model: {model_id}")

# ── 2. Category detection tests ───────────────────────────────────────────────
print("\n-- Category check tests ------------------------------------------------")

TEST_CASES = [
    # (title, company, description, current_category, expected_result)
    (
        "Registered Nurse",
        "HUS Helsinki",
        "We are seeking a registered nurse for our cardiac ward. "
        "You will assist in patient care, medication administration, and daily rounds.",
        "other",
        "healthcare (should be corrected)",
    ),
    (
        "Software Engineer",
        "Futurice Oy",
        "Join our team as a backend developer. You will work with Python, Kubernetes, "
        "and AWS to build scalable microservices for our clients.",
        "it-and-software",
        "it-and-software (should be CORRECT)",
    ),
    (
        "Sales Manager",
        "Nordea Bank",
        "Drive B2B sales in the Nordic market. Manage key accounts, negotiate contracts "
        "and exceed quarterly revenue targets.",
        "healthcare",
        "sales-and-marketing (should be corrected to fix wrong current category)",
    ),
]

# Load categories from the project file
import json
from pathlib import Path
cat_json_path = Path(__file__).parent / "all_jobs_cat.json"
if cat_json_path.exists():
    cat_data = json.loads(cat_json_path.read_text(encoding="utf-8"))
    valid_cats = cat_data.get("categories", [])
else:
    # Fallback minimal list
    valid_cats = [
        "healthcare", "it-and-software", "sales-and-marketing",
        "construction", "education", "engineering", "other",
    ]
    print(f"  (all_jobs_cat.json not found — using minimal fallback list)")

print(f"  Valid categories: {len(valid_cats)} loaded\n")

for i, (title, company, desc, current_cat, note) in enumerate(TEST_CASES, 1):
    print(f"  [{i}] {title}  |  current={current_cat}")
    print(f"       expected: {note}")
    result = cpc._ask_lmstudio(model_id, title, company, desc, current_cat, valid_cats)
    if result is None:
        print(f"       result  : OK CORRECT (category kept as '{current_cat}')\n")
    else:
        print(f"       result  : CORRECTED to '{result}'\n")

print("-- Done ---------------------------------------------------------------\n")
