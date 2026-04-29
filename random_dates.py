import os
import random
import re

slugs = [
    'how-to-get-a-job-in-finland-as-an-international-student',
    '10-mistakes-job-seekers-make-in-finland',
    'jobs-in-finland-that-dont-require-finnish-language',
    'best-cities-in-finland-for-finding-jobs',
    'how-foreigners-can-get-a-job-in-finland',
    'best-job-websites-in-finland-in-2026'
]

# Generate a random date for each slug
slug_dates = {}
for slug in slugs:
    day = random.randint(1, 30)
    slug_dates[slug] = f"April {day}, 2026"

# 1. Update individual blog pages
blog_dir = 'blogs'
for slug in slugs:
    filepath = os.path.join(blog_dir, slug + '.html')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_date = slug_dates[slug]
        # In the blog files, the date is formatted as "Published: April 29, 2026"
        # However, to be safe, replace "April 29, 2026" with new_date
        content = content.replace("April 29, 2026", new_date)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {slug}.html to {new_date}")

# 2. Update blogs.html
blogs_html_path = 'blogs.html'
with open(blogs_html_path, 'r', encoding='utf-8') as f:
    blogs_content = f.read()

for slug in slugs:
    new_date = slug_dates[slug]
    
    # In blogs.html, each article block contains the link and the date.
    # We can match the article block and replace "April 29, 2026" within that block.
    # A block starts with <article and ends with </article>
    
    pattern = re.compile(r'(<article[^>]*>(?:(?!</article>).)*?' + re.escape(slug) + r'(?:(?!</article>).)*?)</article>', re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        block = m.group(1)
        # replace the date
        block = block.replace("April 29, 2026", new_date)
        return block + "</article>"
        
    blogs_content = pattern.sub(repl, blogs_content)

with open(blogs_html_path, 'w', encoding='utf-8') as f:
    f.write(blogs_content)
    
print("Updated blogs.html")

