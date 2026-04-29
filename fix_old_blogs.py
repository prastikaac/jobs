import os
import re

slug_dates = {
    'industry-wise-minimum-wages-in-finland': 'April 14, 2026',
    'tips-and-tricks-for-interview-in-finland': 'April 10, 2026',
    'top-ten-in-demand-jobs-in-finland': 'April 13, 2026'
}

files_to_fix = ['index.html', 'blogs.html']
for filename in os.listdir('blogs'):
    if filename.endswith('.html'):
        files_to_fix.append(f'blogs/{filename}')

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    changed = False
    
    # 1. First, check if the file ITSELF is one of the target blogs, and update its main published date
    basename = os.path.basename(filepath)
    if basename in [s + '.html' for s in slug_dates.keys()]:
        slug = basename.replace('.html', '')
        new_date = slug_dates[slug]
        
        # Replace "Published: August 01, 2026" or similar
        content, n1 = re.subn(r'Published:\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+202\d', f'Published: {new_date}', content)
        # Also replace inside the meta tags or time elements not in <article>
        
        if n1 > 0: changed = True

    # 2. Update any <article> or blocks that contain the slugs
    for slug, new_date in slug_dates.items():
        day = new_date.split(' ')[1].replace(',', '')
        day_pad = day.zfill(2)
        month = new_date.split(' ')[0]
        
        pattern = re.compile(r'(<article[^>]*>(?:(?!</article>).)*?)(' + re.escape(slug) + r')(.*?</article>)', re.DOTALL | re.IGNORECASE)
        
        def repl(m):
            block = m.group(0)
            
            # Replace the datetime attribute
            block = re.sub(r'datetime="202\d-\d{2}-\d{2}([^"]*)"', f'datetime="2026-04-{day_pad}\\1"', block)
            # Replace the title attribute
            block = re.sub(r'title="Posted: [A-Za-z]+ \d{1,2}, 202\d"', f'title="Posted: {new_date}"', block)
            # Replace the inner text of time
            block = re.sub(r'>\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+202\d\s*</time>', f'>{new_date}</time>', block)
            
            return block
            
        content, n2 = pattern.subn(repl, content)
        if n2 > 0: changed = True

    # 3. There is a "Published on — April 10, 2026" in the popular posts widget!
    # Let's replace any "Published on — [Month] [Day], [Year]" specifically for these widgets if they contain the slug.
    for slug, new_date in slug_dates.items():
        # This matches the widget block
        w_pattern = re.compile(r'(<div class="iThmb pThmb">(?:(?!<article class="itm mostP">).)*?)(' + re.escape(slug) + r')(.*?</article>)', re.DOTALL | re.IGNORECASE)
        
        def w_repl(m):
            block = m.group(0)
            block = re.sub(r'Published on &#8212; [A-Za-z]+ \d{1,2}, 202\d', f'Published on &#8212; {new_date}', block)
            return block
            
        content, n3 = w_pattern.subn(w_repl, content)
        if n3 > 0: changed = True

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed dates in {filepath}")

