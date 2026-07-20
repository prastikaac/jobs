"""
test_ai_and_generate.py
  - Picks 3 translated jobs
  - Runs AI generation (what_we_offer / what_we_expect / job_responsibilities)
  - Generates HTML job pages
  - Prints job names + page paths

Usage:  python scraper/test_ai_and_generate.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scraper"))

import ai_processor
import html_generator
import Job_formatter
import config

TRANSLATED_JOBS_PATH = os.path.join("scraper", "data", "translated_jobs.json")
TEST_COUNT = 3
TEST_OFFSET = 3  # skip first N jobs, test the next ones


def main():
    print("Loading translated jobs...")
    with open(TRANSLATED_JOBS_PATH, "r", encoding="utf-8") as f:
        all_jobs = json.load(f)

    candidates = [j for j in all_jobs if j.get("translated_content")]
    print(f"Found {len(candidates)} translated jobs. Testing {TEST_COUNT}...\n")

    results = []

    for i, raw_job in enumerate(candidates[TEST_OFFSET:TEST_OFFSET + TEST_COUNT], 1):
        title = raw_job.get("title", raw_job.get("id", "unknown"))
        text  = raw_job.get("translated_content", "")

        print(f"[{i}/{TEST_COUNT}] AI generating for: {title}")

        # Step 1: AI generation
        ai_data, success, status, err = ai_processor._call_lm_studio_for_content(
            translated_text=text,
            raw_job=raw_job,
            ai_category="other",
        )

        if not success:
            print(f"  ! AI failed: {status} — {err}\n")
            continue

        # Step 2: Generate description + meta
        raw_job["ai_data"] = ai_data
        formatted_desc, meta_desc = ai_processor._generate_description_and_meta(raw_job)
        ai_data["formatted_description"] = formatted_desc
        ai_data["meta_description"]      = meta_desc
        ai_data["job_category"]          = "other"
        raw_job["ai_data"]               = ai_data

        # Step 3: Build the final formatted job (same as pipeline does)
        valid_categories = list(config.VALID_CATEGORIES)
        formatted_job = Job_formatter._build_formatted_job(raw_job, ai_data)

        # Step 4: Generate HTML job page
        page_generated = html_generator.generate_job_page(formatted_job)

        job_id   = formatted_job.get("job_id", "")
        page_url = f"http://localhost:5501/jobs/{job_id}/"

        print(f"  Title:      {formatted_job.get('title')}")
        print(f"  AI title:   {ai_data.get('title')}")
        print(f"  Category:   {formatted_job.get('job_category')}")
        print(f"  Page:       {'GENERATED' if page_generated else 'FAILED'} -> {page_url}")
        print(f"  job_responsibilities ({len(ai_data.get('job_responsibilities', []))}):")
        for x in ai_data.get("job_responsibilities", []):
            print(f"    - {x}")
        print(f"  what_we_expect ({len(ai_data.get('what_we_expect', []))}):")
        for x in ai_data.get("what_we_expect", []):
            print(f"    - {x}")
        print(f"  what_we_offer ({len(ai_data.get('what_we_offer', []))}):")
        for x in ai_data.get("what_we_offer", []):
            print(f"    - {x}")
        print()

        results.append((formatted_job.get("title"), job_id, page_generated))

    print("=" * 60)
    print("SUMMARY — Generated Jobs:")
    for title, job_id, ok in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {title}")
        print(f"        -> http://localhost:5501/jobs/{job_id}/")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
