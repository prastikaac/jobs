import sys
import os

# Ensure scraper dir is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import category_changer

def main():
    if len(sys.argv) != 3:
        print("Usage: python action_change_category.py <job_id> <new_category>")
        sys.exit(1)

    job_id = sys.argv[1].strip()
    new_cat = sys.argv[2].strip()

    print(f"Executing category change for job: '{job_id}' -> '{new_cat}'")

    result = category_changer.change_category(job_id, new_cat)

    if not result.get("ok"):
        print(f"✗ Error: {result.get('error')}")
        sys.exit(1)
        
    print(f"✓ Success! Changed '{job_id}' from '{result.get('old_category')}' to '{result.get('new_category')}'.")
    
    # Print git output
    git_res = result.get("git", {})
    if git_res:
        print("\nGit push log:")
        for msg in git_res.get("messages", []):
            print(f"  {msg}")

if __name__ == "__main__":
    main()
