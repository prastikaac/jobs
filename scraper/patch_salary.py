import json, re, os

TES_PHRASES = [
    'tes:', 'tes ', ' tes', 'ovtes', 'ov-tes', 'tessi', 'asfalttialan', 'kaupan alan',
    'tyoehtosopimus', 'työehtosopimus', 'mukaisesti', 'perustuva', 'palkkausjärjestelmä'
]
CLEAN_SALARY = 'Competitive hourly wage based on Finnish collective agreements.'
DEFAULT_SALARY_TEXT = "Competitive hourly wage based on Finnish collective agreements and other company and links"

def is_tes(s):
    if not s or not isinstance(s, str): return False
    sl = s.lower()
    if any(p in sl for p in TES_PHRASES):
        if '€' not in s and not re.search(r'\d+[\s.-]+\d+', s):
            return True
        if len(s) < 30 and ('tes' in sl or 'ovtes' in sl):
             return True
    return False

def extract_salary_from_text(raw_job: dict) -> str:
    """
    Decide salary in Python from raw structured fields or jobcontent.
    If not found, return the fixed default text.
    """
    from Job_formatter import _clean_text, _looks_finnish
    import translator

    raw_salary = _clean_text(raw_job.get("salary_range", ""))
    text = _clean_text(raw_job.get("jobcontent", ""))

    if raw_salary:
        if is_tes(raw_salary):
            return CLEAN_SALARY

    # Use existing if numeric, otherwise we might need to translate it
    if raw_salary and any(char.isdigit() for char in raw_salary) and "€" in raw_salary:
        return raw_salary

    salary_patterns = [
        r"(\d{1,3}(?:[.,]\d{1,2})?\s*[-–]\s*\d{1,3}(?:[.,]\d{1,2})?\s*€/h)",
        r"(\d{1,3}(?:[.,]\d{1,2})?\s*€/h)",
        r"(\d{1,5}(?:[.,]\d{1,2})?\s*[-–]\s*\d{1,5}(?:[.,]\d{1,2})?\s*€/kk)",
        r"(\d{1,5}(?:[.,]\d{1,2})?\s*€/kk)",
        r"(palkka[:\s]+[^.]{1,40})",
        r"(salary[:\s]+[^.]{1,40})",
        r"(TES[:\s]+[^.]{1,40})",
        r"(according to collective agreement[^.]{0,40})",
    ]

    matched_salary = ""
    for pattern in salary_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            matched_salary = _clean_text(match.group(1))
            break

    # If we have a Finnish looking salary or broad text, translate it
    final_salary = matched_salary or raw_salary
    if final_salary:
        if is_tes(final_salary):
            return CLEAN_SALARY
        if _looks_finnish(final_salary):
            return translator.translate_fi_to_en(final_salary)
        return final_salary

    return DEFAULT_SALARY_TEXT

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

if __name__ == '__main__':
    patch_file('data/jobs.json')
    patch_file('data/rawjobs.json')
    patch_file('data/translated_jobs.json')
