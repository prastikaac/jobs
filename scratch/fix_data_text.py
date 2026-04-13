import re

def fix_data_text(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find <a ... data-text="Value" ...></a> or <a ... data-text="Value" ...>\s*</a>
    # We want to remove data-text="Value" and put "Value" inside the <a> tag.
    # The regex below looks for:
    # 1: `<a `
    # 2: everything before data-text (non-greedy)
    # 3: data-text="([^"]+)"
    # 4: everything after data-text until `>`
    # 5: possible whitespace
    # 6: `</a>`
    
    # We should only replace if there's no text between > and </a>
    # Or just replace all empty/whitespace-only <a> tags that have data-text.
    
    pattern = re.compile(r'(<a\b[^>]*?)\s*data-text="([^"]+)"([^>]*>)\s*</a>', re.IGNORECASE)
    
    def replacer(match):
        pre = match.group(1)
        val = match.group(2)
        post = match.group(3)
        return f"{pre}{post}{val}\n                              </a>"
        
    new_content = pattern.sub(replacer, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Replaced in {filepath}. Occurrences:", len(pattern.findall(content)))

fix_data_text('index.html')
# We could also apply this to other static pages just in case.
for page in ['jobs.html', 'about-us.html', 'contact-us.html', 'privacy-policy.html', 'disclaimer.html', 'terms-and-conditions.html', '404.html']:
    try:
        fix_data_text(page)
    except:
        pass
