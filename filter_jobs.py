import json

# Cleaning sector keywords
CLEANING_KW = ['cleaner', 'cleaning', 'housekeeper', 'housekeeping', 'janitor', 'caretaker',
                'custodian', 'cleaning operative', 'office cleaner', 'window cleaner',
                'domestic cleaner', 'industrial cleaner', 'siivooja', 'siivous',
                'toimitilahuoltaja', 'laitoshuoltaja', 'kiinteistohuolto']

# IT sector keywords
IT_KW = ['software', 'developer', 'programmer', 'it support', 'systems analyst', 'data analyst',
         'web developer', 'backend', 'frontend', 'devops', 'cybersecurity', 'network engineer',
         'database', 'machine learning', 'ai engineer', 'cloud', 'it consultant', 'software engineer',
         'application developer', 'full stack', 'fullstack', 'software architect', 'ict',
         'information technology', 'computer scientist', 'it administrator', 'it manager',
         'system administrator', 'sysadmin', 'helpdesk', 'it technician']

# Restaurant / food sector keywords
RESTAURANT_KW = ['cook', 'chef', 'kitchen', 'restaurant', 'waiter', 'waitress', 'food service',
                 'barista', 'bartender', 'cafe', 'catering', 'dishwasher', 'kitchen hand',
                 'kitchen assistant', 'sous chef', 'head chef', 'line cook', 'commis chef',
                 'kokki', 'tarjoilija', 'ravintolatyontekija', 'keittiöapulainen',
                 'large economy worker', 'culinary']

# Nursing / healthcare sector keywords
NURSING_KW = ['nurse', 'nursing', 'healthcare', 'health care', 'sairaanhoitaja', 'lachihoitaja',
              'lähi', 'carer', 'care worker', 'support worker', 'medical', 'clinical',
              'hospital', 'health assistant', 'ward', 'midwife', 'paramedic',
              'dental nurse', 'psychiatric nurse', 'community nurse', 'registered nurse',
              'health care assistant', 'care assistant', 'home care', 'elderly care',
              'lähihoitaja', 'terveydenhoitaja', 'hoitaja']

def score_job(job, keywords):
    """Return a score based on how many keywords match in the job data."""
    text = ' '.join([
        str(job.get('title', '')),
        str(job.get('jobcategory_keywords', [])),
        str(job.get('translated_job_responsibilities', [])),
        str(job.get('translated_content', '')),
        str(job.get('jobcontent', '')),
    ]).lower()
    
    return sum(1 for kw in keywords if kw.lower() in text)

with open('scraper/data/rawjobs.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total jobs: {len(data)}")

# Score each job for each category
scored = []
for job in data:
    scores = {
        'cleaning': score_job(job, CLEANING_KW),
        'it': score_job(job, IT_KW),
        'restaurant': score_job(job, RESTAURANT_KW),
        'nursing': score_job(job, NURSING_KW),
    }
    best_cat = max(scores, key=lambda k: scores[k])
    best_score = scores[best_cat]
    scored.append((job, scores, best_cat, best_score))

# Sort by score descending, pick top 9 per category (non-overlapping)
selected_ids = set()

def pick_top(category, n=9):
    candidates = [(job, s['cleaning'] if category=='cleaning' else s['it'] if category=='it' else s['restaurant'] if category=='restaurant' else s['nursing'], s) 
                  for job, s, best_cat, best_score in scored
                  if job['id'] not in selected_ids]
    
    if category == 'cleaning':
        candidates = [(job, s['cleaning'], s) for job, s, best_cat, best_score in scored if job['id'] not in selected_ids]
    elif category == 'it':
        candidates = [(job, s['it'], s) for job, s, best_cat, best_score in scored if job['id'] not in selected_ids]
    elif category == 'restaurant':
        candidates = [(job, s['restaurant'], s) for job, s, best_cat, best_score in scored if job['id'] not in selected_ids]
    elif category == 'nursing':
        candidates = [(job, s['nursing'], s) for job, s, best_cat, best_score in scored if job['id'] not in selected_ids]
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    result = []
    for job, score, s in candidates[:n]:
        if score == 0:
            print(f"  WARNING: {category} job has score 0: {job.get('title', 'N/A')}")
        result.append(job)
        selected_ids.add(job['id'])
    return result

cleaning_jobs = pick_top('cleaning', 9)
it_jobs = pick_top('it', 9)
restaurant_jobs = pick_top('restaurant', 9)
nursing_jobs = pick_top('nursing', 9)

print(f"\n--- CLEANING ({len(cleaning_jobs)}) ---")
for j in cleaning_jobs:
    print(f"  {j.get('title', 'N/A')}")

print(f"\n--- IT ({len(it_jobs)}) ---")
for j in it_jobs:
    print(f"  {j.get('title', 'N/A')}")

print(f"\n--- RESTAURANT ({len(restaurant_jobs)}) ---")
for j in restaurant_jobs:
    print(f"  {j.get('title', 'N/A')}")

print(f"\n--- NURSING ({len(nursing_jobs)}) ---")
for j in nursing_jobs:
    print(f"  {j.get('title', 'N/A')}")

total = len(cleaning_jobs) + len(it_jobs) + len(restaurant_jobs) + len(nursing_jobs)
print(f"\nTotal selected: {total}")

# Save filtered jobs with category assigned
final_jobs = []
for j in cleaning_jobs:
    j['detected_category'] = 'cleaning'
    final_jobs.append(j)
for j in it_jobs:
    j['detected_category'] = 'it'
    final_jobs.append(j)
for j in restaurant_jobs:
    j['detected_category'] = 'restaurant'
    final_jobs.append(j)
for j in nursing_jobs:
    j['detected_category'] = 'nursing'
    final_jobs.append(j)

with open('scraper/data/rawjobs.json', 'w', encoding='utf-8') as f:
    json.dump(final_jobs, f, ensure_ascii=False, indent=2)

print(f"\nSaved {len(final_jobs)} jobs to rawjobs.json")
