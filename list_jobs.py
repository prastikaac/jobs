import json

with open('scraper/data/rawjobs.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total jobs: {len(data)}\n")
print("All titles + keywords (for categorization):")
for i, j in enumerate(data):
    title = j.get('title', 'N/A')
    keywords = str(j.get('jobcategory_keywords', []))[:120]
    resp = str(j.get('translated_job_responsibilities', []))[:80]
    print(f"{i:3}: {title[:70]}")
    print(f"       keywords: {keywords}")
    print(f"       resp: {resp}")
    print()
