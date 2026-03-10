import os
import re

old_footer_pattern = r'<!-- Footer - Powered by Zeony -->.*?</footer>'

new_footer = '''<!-- Footer - Powered by Zeony -->
<footer style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 10px 20px; text-align: center; margin-top: auto; border-top: 1px solid #cbd5e1;">
  <div style="display: flex; align-items: center; justify-content: center; gap: 12px;">
    <span style="color: #475569; font-size: 14px; font-weight: 600;">Powered by</span>
    <img src="{{ url_for('static', filename='img/zeony-logo.png') }}" alt="Zeony Technologies" style="height: 40px; width: auto;">
  </div>
</footer>'''

templates_dir = r'C:\Users\Sanjayakumar K\OneDrive\Desktop\ZEONY\Drive Logs\templates'
files_updated = []

for filename in os.listdir(templates_dir):
    if filename.endswith('.html') and filename != 'base.html':
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if footer exists
        if 'Footer - Powered by Zeony' in content:
            # Replace all occurrences of the footer
            new_content = re.sub(old_footer_pattern, new_footer, content, flags=re.DOTALL)
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                files_updated.append(filename)

print(f'Updated {len(files_updated)} files')
for f in files_updated:
    print(f'  - {f}')
