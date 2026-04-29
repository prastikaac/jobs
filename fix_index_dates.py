import os
import re

# Same exact mapping from previous execution
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
    # In index.html, the blog posts are probably enclosed in <article> tags, similar to blogs.html.
    # We find an <article> that contains the slug and replace "April 29, 2026" with new_date.
    pattern = re.compile(r'(<article[^>]*>(?:(?!</article>).)*?' + re.escape(slug) + r'(?:(?!</article>).)*?)</article>', re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        block = m.group(1)
        block = block.replace("April 29, 2026", new_date)
        return block + "</article>"
        
    content = pattern.sub(repl, content)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(content)
    
print("Updated index.html dates!")
