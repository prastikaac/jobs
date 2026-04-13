import re

file_path = r'c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland\index.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern2 = re.compile(r'(<a[^>]*?class="lbN"[^>]*?)(\s*href="[^"]*location=[^"]*")')
new_content2, count2 = pattern2.subn(r'\1 translate="no"\2', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content2)

print(f"Replaced {count2} locations in index.html.")
