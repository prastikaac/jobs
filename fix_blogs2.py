import os
import re

blog_dir = 'blogs'

def fix_links(content, search_text, new_href, new_img):
    # Regex to find the <article> block containing the search_text
    # We use (?:(?!</article>).)*? to ensure we don't span multiple articles
    pattern_str = r'(<article[^>]*>(?:(?!</article>).)*?)(' + re.escape(search_text) + r')((?:(?!</article>).)*?</article>)'
    pattern = re.compile(pattern_str, re.DOTALL | re.IGNORECASE)
    
    def repl(m):
        before = m.group(1)
        match_text = m.group(2)
        after = m.group(3)
        
        block = before + match_text + after
        
        # replace hrefs
        block = re.sub(r'href="[^"]+"', f'href="{new_href}"', block)
        # replace srcs
        block = re.sub(r'src="[^"]+"', f'src="{new_img}"', block)
        block = re.sub(r'data-src="[^"]+"', f'data-src="{new_img}"', block)
        
        return block

    return pattern.sub(repl, content)

for filename in os.listdir(blog_dir):
    if not filename.endswith('.html'): continue
    filepath = os.path.join(blog_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Fix Interview Tips & Tricks
    content = fix_links(
        content,
        "Interview Tips & Tricks for Jobs",
        "https://findjobsinfinland.fi/blogs/tips-and-tricks-for-interview-in-finland",
        "https://findjobsinfinland.fi/images/blogs/tips-and-tricks-for-interview.png"
    )
    
    # 2. Fix Industry-Wise Minimum Wages
    # Note: earlier my regex was just "Industry-Wise\s+Minimum Wages". 
    # Let's match it safely.
    content = fix_links(
        content,
        "Industry-Wise\n                                Minimum Wages",
        "https://findjobsinfinland.fi/blogs/industry-wise-minimum-wages-in-finland",
        "https://findjobsinfinland.fi/images/blogs/industry-wise-minimum-wages.png"
    )
    
    content = fix_links(
        content,
        "Industry-Wise Minimum Wages",
        "https://findjobsinfinland.fi/blogs/industry-wise-minimum-wages-in-finland",
        "https://findjobsinfinland.fi/images/blogs/industry-wise-minimum-wages.png"
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed {filename}")
