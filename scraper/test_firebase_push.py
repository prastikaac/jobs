import json
import sys
import os

# Add root to path so absolute imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import firebase_client

def run_test():
    with open('data/jobs.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Flatten jobs from all sessions
    all_jobs = []
    for session in data:
        all_jobs.extend(session.get('jobs', []))
    
    if not all_jobs:
        print("No jobs found in data/jobs.json")
        return

    # Take last job 
    test_job = all_jobs[-1]
    
    # Change ID to avoid skip
    test_job['id'] = test_job['id'] + '-test-' + str(int(time.time()))
    test_job['title'] = "[TEST-URL] " + test_job.get('title', 'Unknown')
    
    print(f"Testing Firebase alert send for: {test_job['title']}")
    print(f"URL being sent: {test_job.get('jobUrl')}")
    
    firebase_client.init_firebase()
    firebase_client.send_new_job_alerts([test_job])
    print("Done!")

if __name__ == '__main__':
    run_test()
