import sys
import os
import json

# Add current dir to path
sys.path.append(os.getcwd())

from html_generator import generate_job_page

# Sample job with multiple locations
job_multiple = {
    "id": "test_multiple",
    "job_id": "test-job-multiple",
    "title": "Software Developer",
    "company": "Test Company",
    "job_category": "Information Technology",
    "jobLocation": ["Espoo", "Turku", "Helsinki"],
    "description": "This is a test job description."
}

# Sample job with single location
job_single = {
    "id": "test_single",
    "job_id": "test-job-single",
    "title": "Accountant",
    "company": "Finance Corp",
    "job_category": "Finance",
    "jobLocation": ["Tampere"],
    "description": "Single location job."
}

# Dummy template content to test placeholders
template_content = """
<a href="https://findjobsinfinland.fi/jobs?location={-job location link-}" itemprop="item">
  <span itemprop="name">{-job location name-}</span>
</a>
"""

# We need to mock _esc or just use html.escape
import html
def _esc(t): return html.escape(str(t or ""), quote=True)

# Actually, let's just use the real generate_job_page but with a mocked template
# Since it reads from file, I'll create a temporary template file

with open('scraper/temp_template.html', 'w', encoding='utf-8') as f:
    f.write(template_content)

# Mock config
import config
config.JOB_TEMPLATE_PATH = 'scraper/temp_template.html'

# Run generation
for job in [job_multiple, job_single]:
    generate_job_page(job)
    cat_slug = config.slugify_category(job["job_category"])
    job_id = job["job_id"]
    output_path = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug, f"{job_id}.html")
    print(f"--- {job_id} ---")
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Print only relevant lines to avoid console issues
        for line in content.splitlines():
            if 'href="https://findjobsinfinland.fi/jobs?location=' in line or 'itemprop="name"' in line:
                if '{-' not in line: # Only print replaced lines
                     print(line.strip())

# Cleanup
os.remove('scraper/temp_template.html')
# os.remove(output_file)
