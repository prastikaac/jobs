import json

with open('scraper/data/rawjobs.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total jobs: {len(data)}")
print("\nFirst 5 job structures:")
for i, j in enumerate(data[:5]):
    print(f"\n--- Job {i} ---")
    for k, v in j.items():
        val = str(v)[:100] if v else 'N/A'
        print(f"  {k}: {val}")
