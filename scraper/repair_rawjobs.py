import json
import os

with open('data/rawjobs.json', 'rb') as f:
    content = f.read()

text = content.decode('utf-8', errors='replace')

# Manually extract jobs by splitting the array.
# The file starts with "[\n  {" or "[\r\n  {" and ends with "}\n]"
# Let's strip the brackets and split by "},\n  {"
text = text.strip()
if text.startswith('['): text = text[1:]
if text.endswith(']'): text = text[:-1]
text = text.strip()

# Split using a regex to handle variations in spacing
import re
chunks = re.split(r'\},?\s*\{', text)

parsed_jobs = []
broken_chunks = 0

for i, chunk in enumerate(chunks):
    # Re-add the braces to make it a valid JSON object
    chunk_json = '{' + chunk + '}'
    # First and last chunk might have extra braces, let's fix
    if i == 0 and chunk_json.startswith('{{'): chunk_json = chunk_json[1:]
    if i == len(chunks) - 1 and chunk_json.endswith('}}'): chunk_json = chunk_json[:-1]
    
    try:
        job = json.loads(chunk_json)
        parsed_jobs.append(job)
    except Exception as e:
        # Try some basic repairs for the chunk
        fixed_chunk = chunk_json
        
        # Fix missing closing quotes before comma newline
        fixed_chunk = re.sub(r'([^\"]),\s*"source":', r'\1",\n  "source":', fixed_chunk)
        # Fix invalid escapes (like \ufffd or \\)
        fixed_chunk = fixed_chunk.replace('\ufffd', '')
        fixed_chunk = fixed_chunk.replace('\\,\n', '",\n')
        fixed_chunk = fixed_chunk.replace('\\,\r\n', '",\r\n')
        
        # Remove any literal control characters except \n, \r, \t
        fixed_chunk = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', fixed_chunk)
        
        try:
            job = json.loads(fixed_chunk)
            parsed_jobs.append(job)
        except Exception as e2:
            broken_chunks += 1
            # print(f"Chunk {i} broken: {e2}")

print(f"Recovered {len(parsed_jobs)} jobs. Lost {broken_chunks} chunks.")

with open('data/rawjobs.json', 'w', encoding='utf-8') as f:
    json.dump(parsed_jobs, f, ensure_ascii=False, indent=2, default=str)
print("Saved repaired rawjobs.json")
