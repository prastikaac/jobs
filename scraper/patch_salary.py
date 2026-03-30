import json, re, os

TES_PHRASES = [
    'tes:', 'tes ', ' tes', 'ovtes', 'ov-tes', 'tessi', 'asfalttialan', 'kaupan alan',
    'tyoehtosopimus', 'työehtosopimus', 'mukaisesti', 'perustuva', 'palkkausjärjestelmä'
]
CLEAN_SALARY = 'Competitive hourly wage based on Finnish collective agreements.'

def is_tes(s):
    if not s or not isinstance(s, str): return False
    sl = s.lower()
    if any(p in sl for p in TES_PHRASES):
        if '€' not in s and not re.search(r'\d+[\s.-]+\d+', s):
            return True
        if len(s) < 30 and ('tes' in sl or 'ovtes' in sl):
             return True
    return False

def patch_file(path):
    if not os.path.exists(path):
        print(f'File {path} not found.')
        return
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fixed = 0
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict) and 'jobs' in data[0]:
            for session in data:
                for job in session.get('jobs', []):
                    if is_tes(job.get('salary_range')):
                        job['salary_range'] = CLEAN_SALARY
                        fixed += 1
        else:
            for job in data:
                if is_tes(job.get('salary_range')):
                    job['salary_range'] = CLEAN_SALARY
                    fixed += 1
                    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Patched {fixed} jobs in {path}')

patch_file('data/jobs.json')
patch_file('data/rawjobs.json')
patch_file('data/translated_jobs.json')
