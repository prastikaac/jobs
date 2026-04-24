import json
import urllib.request
import urllib.error

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "qwen2.5-coder-1.5b-instruct"

_PROMPT_TMPL = """\
You are an expert job classifier. Look at the Job Title.
Select the single best matching category from the Valid Categories list.

Job Title: {title}

Valid Categories:
{cat_list}

Output exactly one word (the exact category slug). No explanation.
Answer:
"""

def test_category_check(title, current_category, valid_cats):
    cat_list = "\n".join(f"- {c}" for c in valid_cats)
    prompt = _PROMPT_TMPL.format(
        title=title,
        cat_list=cat_list
    )
    
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that strictly follows instructions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 16,
        "stream": False,
    }
    
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
            result = data["choices"][0]["message"]["content"].strip()
            print(f"Title: {title}")
            print(f"LM Studio Output: '{result}'\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    valid_categories = ["it-and-software", "healthcare-and-medical", "education", "construction"]
    
    test_category_check(
        title="Senior Python Backend Developer", 
        current_category="healthcare-and-medical", 
        valid_cats=valid_categories
    )
    
    test_category_check(
        title="Registered Nurse (RN)", 
        current_category="healthcare-and-medical", 
        valid_cats=valid_categories
    )
