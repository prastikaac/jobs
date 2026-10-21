import os
import sys
import json
import re
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TARGET_ID = "b0e29da7"
TARGET_SLUG = "tarzan-the-bitch-or-jane-espoo-b0e29da7"

print(f"Purging job ID {TARGET_ID} and slug {TARGET_SLUG}...")

# 1. Delete HTML files
jobs_dir = os.path.join(BASE_DIR, "jobs")
deleted_html = []
for root, dirs, files in os.walk(jobs_dir):
    for f in files:
        if TARGET_ID in f or TARGET_SLUG in f:
            full_path = os.path.join(root, f)
            os.remove(full_path)
            deleted_html.append(full_path)
            print(f"[HTML] Deleted: {full_path}")

if not deleted_html:
    print("[HTML] No matching HTML files found.")

# 2. Clean sitemap-jobs.xml
sitemap_path = os.path.join(BASE_DIR, "sitemap-jobs.xml")
if os.path.exists(sitemap_path):
    with open(sitemap_path, "r", encoding="utf-8") as f:
        sitemap_content = f.read()
    
    # Remove <url> blocks containing the target
    pattern = re.compile(rf"\s*<url>\s*<loc>[^<]*{TARGET_ID}[^<]*<\/loc>.*?<\/url>", re.DOTALL)
    new_sitemap, count = pattern.subn("", sitemap_content)
    if count > 0:
        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(new_sitemap)
        print(f"[Sitemap] Removed {count} entry/entries from sitemap-jobs.xml")
    else:
        print("[Sitemap] No matching entries in sitemap-jobs.xml")

# 3. Clean main JSON vault
vault_dir = os.path.join(BASE_DIR, "xQ7mPfL92aKdR8vTnW3sYhU6cZe1BjFoP4rNxLmQa8VtHyC2dKsJwE9uGbRfXpLoM5qZaNcV7tHyD3kWsPbXeR8mQvT1uJnFyL6cKdSaP9wEr")
main_json_path = os.path.join(vault_dir, "pfbID9xRtQw7LmNzE4vHyK2sDaFc8PqW1uJmXoT5rVeYbCnL6kHsAzG3dRfUpQoXnT8vLmKeP2sHyW7cDaJfR9uGbNxQ4tVeMzLpKoY1xCfHsRw8nTaVqZdE6mPyUi.json")

if os.path.exists(main_json_path):
    with open(main_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    initial_count = len(data)
    new_data = []
    removed = 0
    
    # Handle both list of jobs and list of groups
    for item in data:
        if isinstance(item, dict):
            # Check if this item is a job or a group with 'jobs'
            if "jobs" in item and isinstance(item["jobs"], list):
                before = len(item["jobs"])
                item["jobs"] = [j for j in item["jobs"] if j.get("id") != TARGET_ID and TARGET_ID not in j.get("job_id", "") and TARGET_SLUG not in j.get("job_id", "")]
                removed += (before - len(item["jobs"]))
                new_data.append(item)
            else:
                if item.get("id") == TARGET_ID or TARGET_ID in item.get("job_id", "") or TARGET_SLUG in item.get("job_id", ""):
                    removed += 1
                else:
                    new_data.append(item)
        else:
            new_data.append(item)
            
    if removed > 0:
        with open(main_json_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        print(f"[Main JSON] Successfully removed {removed} job(s) from main database JSON.")
    else:
        print("[Main JSON] Target job not found in main database JSON.")

# 4. Clean scraper/data JSON files
data_dir = os.path.join(BASE_DIR, "scraper", "data")
for filename in ["rawjobs.json", "formatted_jobs.json", "translated_jobs.json", "ai_proccessed_jobs.json"]:
    filepath = os.path.join(data_dir, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 2:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, list):
                orig_len = len(d)
                d = [j for j in d if j.get("id") != TARGET_ID and TARGET_ID not in j.get("job_id", "") and TARGET_SLUG not in j.get("job_id", "")]
                if len(d) < orig_len:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(d, f, indent=2, ensure_ascii=False)
                    print(f"[{filename}] Removed {orig_len - len(d)} record(s).")
        except Exception as e:
            print(f"[{filename}] Error cleaning: {e}")

# 5. Clean processing_state.json
state_path = os.path.join(data_dir, "processing_state.json")
if os.path.exists(state_path) and os.path.getsize(state_path) > 2:
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        modified = False
        if isinstance(state, dict):
            for k, v in state.items():
                if isinstance(v, list) and TARGET_ID in v:
                    state[k] = [x for x in v if x != TARGET_ID]
                    modified = True
                elif isinstance(v, dict) and TARGET_ID in v:
                    del v[TARGET_ID]
                    modified = True
        if modified:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print("[processing_state.json] Cleaned target ID.")
    except Exception as e:
        print(f"[processing_state.json] Error cleaning: {e}")

print("PURGE COMPLETE!")
