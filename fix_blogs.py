import os
from bs4 import BeautifulSoup

blog_dir = 'blogs'
target_img = 'https://findjobsinfinland.fi/images/blogs/industry-wise-minimum-wages.png'
target_link = 'https://findjobsinfinland.fi/blogs/industry-wise-minimum-wages-in-finland'

for filename in os.listdir(blog_dir):
    if not filename.endswith('.html'): continue
    filepath = os.path.join(blog_dir, filename)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
        
    soup = BeautifulSoup(html, 'html.parser')
    changed = False
    
    # Find the article containing "Industry-Wise Minimum Wages"
    for article in soup.find_all('article', class_='itm mostP'):
        if 'Industry-Wise' in article.get_text():
            # Fix links
            for a in article.find_all('a'):
                if a.has_attr('href'):
                    a['href'] = target_link
                    changed = True
                    
            # Fix images
            for img in article.find_all('img'):
                if img.has_attr('src'):
                    img['src'] = target_img
                    changed = True
                if img.has_attr('data-src'):
                    img['data-src'] = target_img
                    changed = True
                    
    if changed:
        # Instead of writing the soup output (which might mess up formatting), 
        # let's write a regex that specifically targets this article's content in the raw text, 
        # or since BS4 might reformat things, we can use a more precise regex.
        pass

# Actually, BS4 might change formatting. Let's do it with regex to be safe.
import re

for filename in os.listdir(blog_dir):
    if not filename.endswith('.html'): continue
    filepath = os.path.join(blog_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the article block
    pattern = re.compile(r'(<article class="itm mostP">.*?)Industry-Wise\s+Minimum Wages(.*?)</article>', re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        block = m.group(1) + 'Industry-Wise\n                                Minimum Wages' + m.group(2)
        # replace all href="..."
        block = re.sub(r'href="[^"]+"', f'href="{target_link}"', block)
        # replace all src="..."
        block = re.sub(r'src="[^"]+"', f'src="{target_img}"', block)
        # replace all data-src="..."
        block = re.sub(r'data-src="[^"]+"', f'data-src="{target_img}"', block)
        
        # We might accidentally replace hrefs we shouldn't? There are only a few in this block.
        # href for .thmb, href for .unclicklocation, href for .iTtl a. All should point to the target_link.
        return block + '</article>'

    new_content = pattern.sub(repl, content)
    
    # Also fix blogs-template.html if it has {--blogs url--} instead of the real URL
    # Because my regex replaced all hrefs with target_link, if blogs-template.html had href="{--blogs url--}", it got replaced with target_link!
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {filename}")
