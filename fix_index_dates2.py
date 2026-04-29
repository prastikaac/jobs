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
    # Extract day
    day = new_date.split(' ')[1].replace(',', '')
    day_pad = day.zfill(2)
    
    # In index.html, the blog posts might be within an element containing the slug
    # A <div class="itm"> or <article class="itm"> or similar...
    # Let's search for the block containing the slug href and ending at </article> or </div>... 
    # Wait, the best way is to match from href="...slug..." up to </time> or something, or find the <time> tag preceding the slug?
    
    # Actually, in index.html, the structure usually is:
    # <div class="someClass">
    #   <time ...>...</time>
    #   <a href="...slug...">
    # ...
    
    # Let's do a more robust regex. We want to find the <time> tag that belongs to this slug.
    # The <time> tag might appear BEFORE the slug in index.html!
    # Let's find <time ...>...</time> \s* <div ...> <a ...href="...slug...">
    
    # Since we know there are exactly 13 occurrences of "April 29, 2026" and we know the slugs,
    # let's just do a regex that matches `<time ... title="Posted: April 29, 2026">April\s+29, 2026</time>` 
    # and the slug nearby.
    
    # A safer approach: find the <time> block that is closest to the slug.
    # Wait, in index.html, there are 19 occurrences originally, 13 left. So some were already changed?
    # No, 19 occurrences of the string "April 29, 2026" means maybe 6 * 2 (title + content) = 12 ? Plus some others?
    pass

# Let's just find the exact block for each slug in index.html
# Let's use BeautifulSoup
from bs4 import BeautifulSoup

with open(index_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Instead of parsing with bs4 which might destroy formatting, let's use regex with Lookahead/Lookbehind or just careful splitting.
# We will split the content by `<time class="aTtmp pTtmp pbl"` and then for each chunk, check if it contains the slug.
# Wait, the chunk might contain multiple slugs if we split by time.
# Let's split by `<article` or `<div class="pSnpt"` or whatever contains the single post.

# Let's look at the DOM structure of index.html for a post:
# <article class="itm">
#   ...
#   <time class="aTtmp pTtmp pbl" datetime="2026-04-29" title="Posted: April 29, 2026">April\n 29, 2026</time>
#   ...
#   <a href="...slug...">...</a>
# </article>

content_new = content
for slug, new_date in slug_dates.items():
    day = new_date.split(' ')[1].replace(',', '')
    day_pad = day.zfill(2)
    
    # Regex to find <article>...</article> containing the slug
    # We will replace the datetime, title, and the inner text of <time> inside this article.
    
    pattern = re.compile(r'(<article[^>]*>(?:(?!</article>).)*?)(' + re.escape(slug) + r')(.*?</article>)', re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        block = m.group(0)
        
        # Replace datetime
        block = re.sub(r'datetime="2026-04-29"', f'datetime="2026-04-{day_pad}"', block)
        # Replace title
        block = re.sub(r'title="Posted: April 29, 2026"', f'title="Posted: {new_date}"', block)
        # Replace inner text of time
        block = re.sub(r'>April\s+29,\s+2026</time>', f'>{new_date}</time>', block)
        
        return block
        
    content_new = pattern.sub(repl, content_new)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(content_new)

print("Updated index.html dates accurately!")

