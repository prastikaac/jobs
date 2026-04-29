import re
import datetime

files_to_check = ['index.html', 'blogs.html']

for filename in files_to_check:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            html = f.read()
            
        print(f"--- {filename} ---")
        
        # In both index.html and blogs.html, we need to find the container that holds multiple blogs
        # They usually are <article class="itm"> or similar within a main block.
        # But wait, index.html has a Pinned Post, then Popular Posts in the sidebar. We want to sort the main blog feed!
        # Actually, let's look for all articles with a publish date.
        
        articles = re.findall(r'(<article class="itm(?:(?!<article).)*?</article>)', html, re.DOTALL)
        print(f"Found {len(articles)} articles.")
        for i, a in enumerate(articles):
            # find title
            m_title = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', a, re.DOTALL)
            title = m_title.group(1).strip() if m_title else "No Title"
            
            # find date
            m_date = re.search(r'<time[^>]*datetime="([^"]+)"', a)
            date_str = m_date.group(1) if m_date else "No Date"
            
            print(f"  {i}: {title} | {date_str}")
            
    except Exception as e:
        print(f"Error on {filename}: {e}")
