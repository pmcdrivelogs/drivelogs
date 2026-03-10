import os
import re

# Pattern to match the footer
footer_pattern = r'<!-- Footer - Powered by Zeony -->.*?</footer>\s*'

templates_dir = r'C:\Users\Sanjayakumar K\OneDrive\Desktop\ZEONY\Drive Logs\templates'
files_updated = []

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if footer exists
        if 'Footer - Powered by Zeony' in content:
            # Remove all occurrences of the footer
            new_content = re.sub(footer_pattern, '', content, flags=re.DOTALL)
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_updated.append(filename)

print(f'Removed footer from {len(files_updated)} files')
for f in files_updated:
    print(f'  - {f}')
