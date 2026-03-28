"""
Export all Jinja2 templates in the `templates/` folder to PDF files.

How it works:
- Loads the Flask app from `app.py` and enters an `app.app_context()` so we can call
  `render_template()` for each template file.
- Renders each template with a conservative default context (a large dict of keys set to
  safe empty/zero values) to avoid missing-variable errors.
- Writes the rendered HTML to a temporary file and invokes `wkhtmltopdf` to produce a PDF.

Requirements:
- Python dependencies: none beyond Flask (the app already depends on Flask).
- System dependency: `wkhtmltopdf` must be installed and on PATH. On Windows, download
  and install from https://wkhtmltopdf.org/ and ensure the folder containing
  `wkhtmltopdf.exe` is in your PATH.

Usage (from project root):
    python export_all_templates_to_pdf.py

Output:
- PDFs are created under `exports/pdfs/` with names like `templates--admin_analytics_dashboard.html.pdf`.

If you want, I can adjust the default context values or attempt to auto-detect template variables.
"""

import os
import sys
import glob
import subprocess
from pathlib import Path

# Ensure project root is on path and app can be imported
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from flask import render_template
    from app import app
except Exception as e:
    print("ERROR: Could not import Flask app. Make sure you run this from the project root and that app.py is importable.")
    print("Import error:", e)
    raise

TEMPLATES_DIR = PROJECT_ROOT / 'templates'
OUT_DIR = PROJECT_ROOT / 'exports' / 'pdfs'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Conservative default context: include many keys the templates may reference
DEFAULT_CONTEXT = {
    # stock inventory
    'total_items': 0,
    'total_value': '0.00',
    'instock_value': '0.00',
    'total_utilized': 0,
    'total_scrapped': 0,
    'utilized_value': '0.00',
    'scrapped_value': '0.00',
    'active_items': 0,
    'vendors': [],
    'purchase_types': [],
    'items': [],
    'issued_items': [],
    'utilization_records': [],
    'scrap_records': [],
    # analytics
    'daily_data': {},
    'weekly_data': {},
    'monthly_data': {},
    'total_purchases': 0,
    'total_purchase_value': 0,
    'total_utilization': 0,
    'total_scrap': 0,
    'total_issues': 0,
    'overall_stock_totals': {},
    'driver_salary': 0,
    'rate_and_taxes': 0,
    # generic
    'maintenance_corrected': [],
    'maintenance_pending': [],
    'all_vehicles_data': [],
    'top_vehicles': [],
    'active_drivers': 0,
    'past_drivers': 0,
    'compliant_count': 0,
    'due_soon_count': 0,
    'overdue_count': 0,
}

# Extra: allow the script to accept optional templates list via args
args = sys.argv[1:]
if args:
    # template names passed on CLI
    templates_to_process = []
    for a in args:
        p = (TEMPLATES_DIR / a)
        if p.exists():
            templates_to_process.append(str(p))
        else:
            # allow passing just the filename
            candidates = list(TEMPLATES_DIR.glob(a))
            templates_to_process.extend([str(c) for c in candidates])
else:
    templates_to_process = [str(p) for p in TEMPLATES_DIR.glob('**/*.html')]

if not templates_to_process:
    print('No templates found under templates/. Nothing to do.')
    sys.exit(1)

print(f'Found {len(templates_to_process)} templates. Rendering and exporting to PDFs...')

# Helper to run wkhtmltopdf
def wkhtmltopdf(html_path, pdf_path):
    cmd = ['wkhtmltopdf', '--enable-local-file-access', html_path, pdf_path]
    try:
        subprocess.check_call(cmd)
        return True
    except FileNotFoundError:
        print('ERROR: wkhtmltopdf not found. Install it and ensure it is on your PATH.')
        return False
    except subprocess.CalledProcessError as e:
        print('wkhtmltopdf failed:', e)
        return False

with app.app_context():
    for tpl_path in templates_to_process:
        tpl_rel = os.path.relpath(tpl_path, TEMPLATES_DIR)
        tpl_name = tpl_rel.replace(os.sep, '--')
        try:
            # render template using its filename relative to templates/
            # e.g., for templates/admin_analytics_dashboard.html use 'admin_analytics_dashboard.html'
            render_name = tpl_rel.replace('\\', '/').lstrip('/')
            print('Rendering', render_name)
            html = render_template(render_name, **DEFAULT_CONTEXT)
        except Exception as e:
            print(f'Warning: rendering {render_name} raised an exception. Trying to render with an empty context. Error: {e}')
            try:
                html = render_template(render_name)
            except Exception as e2:
                print(f'Skipping {render_name}: cannot render. Error: {e2}')
                continue

        tmp_html = OUT_DIR / (tpl_name + '.html')
        pdf_out = OUT_DIR / (tpl_name + '.pdf')
        tmp_html.write_text(html, encoding='utf-8')

        ok = wkhtmltopdf(str(tmp_html), str(pdf_out))
        if ok:
            print('Written', pdf_out)
        else:
            print('Failed to create PDF for', render_name)

print('Done. PDFs are in', str(OUT_DIR))
print('If wkhtmltopdf was not installed, see https://wkhtmltopdf.org/ for downloads and install instructions.')
