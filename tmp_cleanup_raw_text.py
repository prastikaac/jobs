import json
import os

files_to_clean = [
    r"c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper\data\rawjobs.json",
    r"c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\scraper\data\jobs.json"
]

for file_path in files_to_clean:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        modified = False
        if isinstance(data, list):
            for item in data:
                # If it's the rawjobs structure (list of jobs)
                if isinstance(item, dict) and "raw_text" in item:
                    del item["raw_text"]
                    modified = True
                
                # If it's the jobs structure (list of objects with "jobs" key)
                if isinstance(item, dict) and "jobs" in item:
                    for job in item["jobs"]:
                        if "raw_text" in job:
                            del job["raw_text"]
                            modified = True
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Cleaned: {file_path}")
        else:
            print(f"No 'raw_text' found in: {file_path}")
            
    except Exception as e:
        print(f"Error cleaning {file_path}: {e}")
