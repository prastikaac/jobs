import json
import sys
from collections import Counter

# jobs.json is a list of {scrape_timestamp, jobs:[...]} batches
with open('data/jobs.json', encoding='utf-8') as f:
    raw = json.load(f)

# Flatten all jobs from all batches
all_jobs = []
for batch in raw:
    all_jobs.extend(batch.get('jobs', []))

print(f'Total jobs: {len(all_jobs)}')

issues = []

def check_field(field_name, items):
    field_issues = []
    if not items:
        field_issues.append('EMPTY_LIST: field has no items at all')
        return field_issues
    for i, item in enumerate(items):
        if not isinstance(item, str):
            field_issues.append(f'NOT_STRING item[{i}]: type={type(item).__name__}')
            continue
        stripped = item.strip()
        if not stripped:
            field_issues.append(f'BLANK_ITEM item[{i}]: empty string')
            continue
        # Missing trailing period
        if stripped[-1] not in '.!?':
            field_issues.append(f'NO_PERIOD item[{i}]: "{stripped[:120]}"')
        # Too long — paragraph dumped as a bullet
        if len(stripped) > 200:
            field_issues.append(f'TOO_LONG({len(stripped)}chars) item[{i}]: "{stripped[:120]}..."')
        # Filler / intro text that leaked into list
        filler_phrases = [
            'qualities mentioned below', 'listed below', 'as follows',
            'include the following', 'so welcome to', 'welcome to raahe',
            'eligibility requirement', 'qualities we expect',
            'this opportunity is for', 'we are looking for',
        ]
        for g in filler_phrases:
            if g.lower() in stripped.lower():
                field_issues.append(f'FILLER_TEXT item[{i}]: "{stripped[:120]}"')
                break
        # Cross-contamination: requirements content in offer list
        if field_name == 'what_we_offer':
            req_kw = [
                'degree required', 'experience required', 'must have',
                'eligibility requirement', 'vaccination', 'qualification required',
                'valid license', 'nursing degree',
            ]
            for kw in req_kw:
                if kw.lower() in stripped.lower():
                    field_issues.append(f'WRONG_FIELD(requirement_in_offer) item[{i}]: "{stripped[:120]}"')
                    break
        # Cross-contamination: offer content in requirements list
        if field_name == 'what_we_expect':
            offer_kw = [
                'we offer', 'paid leave', 'health insurance', 'pension',
                'free lunch', 'trial period', 'professional work environment',
                'competitive salary', 'benefits',
            ]
            for kw in offer_kw:
                if kw.lower() in stripped.lower():
                    field_issues.append(f'WRONG_FIELD(offer_in_requirements) item[{i}]: "{stripped[:120]}"')
                    break
        # Non-responsibility content in responsibilities
        if field_name == 'job_responsibilities':
            non_resp_kw = [
                'trial period', 'we offer', 'professional work environment',
                'nursing degree', 'eligibility requirement', 'vaccination',
                'so welcome', 'degree or', 'qualification',
            ]
            for kw in non_resp_kw:
                if kw.lower() in stripped.lower():
                    field_issues.append(f'WRONG_FIELD(non_responsibility_in_resp) item[{i}]: "{stripped[:120]}"')
                    break
    return field_issues

for job in all_jobs:
    job_id = job.get('id', job.get('job_id', 'unknown'))
    title  = job.get('title', '')
    resp   = job.get('job_responsibilities', [])
    expect = job.get('what_we_expect', [])
    offer  = job.get('what_we_offer', [])

    r_issues = check_field('job_responsibilities', resp)
    e_issues = check_field('what_we_expect', expect)
    o_issues = check_field('what_we_offer', offer)

    if r_issues or e_issues or o_issues:
        issues.append({
            'id': job_id,
            'title': title,
            'responsibilities_issues': r_issues,
            'expect_issues': e_issues,
            'offer_issues': o_issues,
            'resp_data': resp,
            'expect_data': expect,
            'offer_data': offer,
        })

print(f'Jobs with issues: {len(issues)} / {len(all_jobs)}')

# Aggregate
r_types = Counter()
e_types = Counter()
o_types = Counter()
for iss in issues:
    for s in iss['responsibilities_issues']:
        r_types[s.split(' ')[0]] += 1
    for s in iss['expect_issues']:
        e_types[s.split(' ')[0]] += 1
    for s in iss['offer_issues']:
        o_types[s.split(' ')[0]] += 1

print()
print('=== Responsibilities issue types ===')
for k, v in r_types.most_common():
    print(f'  {v:4d}x  {k}')

print()
print('=== What We Expect issue types ===')
for k, v in e_types.most_common():
    print(f'  {v:4d}x  {k}')

print()
print('=== What We Offer issue types ===')
for k, v in o_types.most_common():
    print(f'  {v:4d}x  {k}')

# Sample one job per issue type
print()
print('=== Sample entries per issue type ===')
for section_label, data_key, iss_key in [
    ('RESPONSIBILITIES', 'resp_data',   'responsibilities_issues'),
    ('WHAT WE EXPECT',  'expect_data',  'expect_issues'),
    ('WHAT WE OFFER',   'offer_data',   'offer_issues'),
]:
    print(f'\n--- {section_label} ---')
    seen = set()
    for iss in issues:
        for issue_str in iss[iss_key]:
            itype = issue_str.split(' ')[0]
            if itype in seen:
                continue
            seen.add(itype)
            print(f'  Type: {itype}')
            print(f'  Job:  {iss["title"]!r} ({iss["id"]})')
            print(f'  Msg:  {issue_str}')
            print(f'  Data: {iss[data_key]}')
            print()

with open('data/ai_field_issues.json', 'w', encoding='utf-8') as f:
    json.dump(issues, f, ensure_ascii=False, indent=2)
print(f'Full details saved to data/ai_field_issues.json ({len(issues)} jobs)')
