import os
import re

slug_dates = {
    'how-to-get-a-job-in-finland-as-an-international-student': 'April 8, 2026',
    '10-mistakes-job-seekers-make-in-finland': 'April 27, 2026',
    'jobs-in-finland-that-dont-require-finnish-language': 'April 9, 2026',
    'best-cities-in-finland-for-finding-jobs': 'April 30, 2026',
    'how-foreigners-can-get-a-job-in-finland': 'April 22, 2026',
    'best-job-websites-in-finland-in-2026': 'April 28, 2026'
}

index_path = 'index.html'

with open(index_path, 'r', encoding='utf-8') as f:
    content = f.read()

for slug, new_date in slug_dates.items():
    day = new_date.split(' ')[1].replace(',', '')
    day_pad = day.zfill(2)
    
    pattern = re.compile(r'(<article[^>]*>(?:(?!</article>).)*?)(' + re.escape(slug) + r')(.*?</article>)', re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        block = m.group(0)
        # Fix datetime with timezone
        block = re.sub(r'datetime="2026-04-29([^"]*)"', f'datetime="2026-04-{day_pad}\\1"', block)
        return block
        
    content = pattern.sub(repl, content)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed datetime attributes in index.html!")
