import os

footer_html = '''
<!-- Footer - Powered by Zeony -->
<footer style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 12px 20px; text-align: center; margin-top: auto;">
  <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
    <span style="color: #94a3b8; font-size: 12px; font-weight: 500;">Powered by</span>
    <img src="{{ url_for('static', filename='img/zeony-logo.png') }}" alt="Zeony Technologies" style="height: 28px; width: auto;">
  </div>
</footer>
'''

# Use absolute path
templates_dir = r'C:\Users\Sanjayakumar K\OneDrive\Desktop\ZEONY\Drive Logs\templates'
files_updated = []

for filename in os.listdir(templates_dir):
    if filename.endswith('.html') and filename != 'base.html':
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip if footer already exists
        if 'Powered by Zeony' in content:
            continue
        
        # Find </body> and insert footer before it
        if '</body>' in content:
            new_content = content.replace('</body>', footer_html + '</body>')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            files_updated.append(filename)

print(f'Updated {len(files_updated)} files')
for f in files_updated:
    print(f'  - {f}')
