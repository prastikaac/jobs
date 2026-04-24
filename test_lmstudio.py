import json
import urllib.request
import urllib.error

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "qwen2.5-coder-1.5b-instruct"

def test_system_prompt():
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Hello"
            }
        ],
        "temperature": 0.0,
        "max_tokens": 50,
        "stream": False,
    }
    
    req = urllib.request.Request(
        LM_STUDIO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            print("System Prompt Test: SUCCESS")
    except urllib.error.HTTPError as exc:
        print("System Prompt Test: HTTP", exc.code)
        print(exc.read().decode('utf-8'))
    except Exception as e:
        print("System Prompt Test: ERROR", e)

if __name__ == "__main__":
    test_system_prompt()
