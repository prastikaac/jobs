import os

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace 'Information Technology' with 'Information Technology (IT)'
        # But make sure we don't accidentally do 'Information Technology (IT) (IT)'
        # So we first replace 'Information Technology (IT)' with 'Information Technology'
        # and then replace 'Information Technology' with 'Information Technology (IT)'
        
        # Actually safer:
        content = content.replace('Information Technology (IT)', 'Information Technology')
        content = content.replace('Information Technology', 'Information Technology (IT)')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def walk_dir(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                replace_in_file(os.path.join(root, file))

if __name__ == '__main__':
    walk_dir('.')
    print("Done replacing.")
