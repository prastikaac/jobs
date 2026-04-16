import json
import sys
import os

# Add root to path so absolute imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import firebase_client

def run_test():
    import time
    
    test_job = {
        "id": "gmail-test-" + str(int(time.time())),
        "title": "Software Developer - Helsinki (Test)",
        "company": "FindJobsInFinland",
        "jobUrl": "https://findjobsinfinland.fi/jobs",
        "description": "This is a test alert to verify Gmail SMTP delivery is working correctly.",
        "jobLocation": [],
        "jobCategory": [],
        "jobTimes": [],
        "jobType": [],
        "jobLanguages": [],
        "date_posted": "2026-04-14",
        "date_expires": "2026-05-14"
    }
    
    print(f"Testing Firebase alert send for: {test_job.get('title')}")
    print(f"URL being sent: {test_job.get('jobUrl')}")
    
    firebase_client.init_firebase()
    firebase_client.send_new_job_alerts([test_job])
    print("Done!")

if __name__ == '__main__':
    run_test()
