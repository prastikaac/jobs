import json
import os

raw_path = r"c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper\data\rawjobs.json"

if os.path.exists(raw_path):
    with open(raw_path, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    for job in jobs:
        # Delete the array fields to force a re-translation.
        # We can leave translated_content alone if the description translated well, 
        # but the user specifically complained about what_we_expect and job_responsibilities.
        keys_to_delete = [
            "translated_what_we_expect",
            "translated_job_responsibilities",
            "translated_what_we_offer",
            "translated_who_is_this_for"
        ]
        for key in keys_to_delete:
            if key in job:
                del job[key]

    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    print("Cleared cached translated list fields from rawjobs.json")
else:
    print("rawjobs.json not found")
