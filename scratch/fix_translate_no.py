import re

def fix_translate_no(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find <a ... href="https://findjobsinfinland.fi/jobs?location=helsinki" ...>
    # We want to add translate="no" to these a tags if they don't already have it.
    
    # Simple regex to find the elements with class="lbN" containing href="...location=..."
    # The user example:
    # <li><a aria-label="Helsinki" class="lbN" translate="no" href="..."

    def replacer(match):
        tag = match.group(0)
        if 'translate=' in tag:
            # If translate="" or translate="no" exists
            tag = re.sub(r'translate="[^"]*"', 'translate="no"', tag)
            return tag
        else:
            return tag.replace('<a ', '<a translate="no" ')

    # only for location links
    pattern = re.compile(r'<a[^>]+href="[^"]*location=[^"]*"[^>]*>', re.IGNORECASE)
    
    new_content = pattern.sub(replacer, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Replaced translate=no in {filepath}. Matches: {len(pattern.findall(content))}")

fix_translate_no('scraper/job_template.html')

