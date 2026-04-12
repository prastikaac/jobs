import json
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)

# Needs to run within scraper directory context correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from html_generator import _generate_jobs_table_page

with open(config.JOBS_JSON_PATH, 'r', encoding='utf-8') as f:
    jobs = json.load(f)
    
_generate_jobs_table_page(jobs)
