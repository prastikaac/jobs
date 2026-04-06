import json
import sys
import os

# Add scraper to path so absolute imports work
sys.path.insert(0, os.path.abspath('.'))

from scraper import firebase_client

def run_test():
    with open('scraper/data/formatted_jobs_flat.json', 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    # Take last job 
    test_job = jobs[-1]
    
    # Change ID to avoid skip
    test_job['id'] = test_job['id'] + '-test-preferences-push'
    test_job['title'] = "[TEST] " + test_job.get('title', 'Unknown')
    
    print("Testing Firebase alert send...")
    firebase_client.send_new_job_alerts([test_job])
    print("Done!")

if __name__ == '__main__':
    run_test()
