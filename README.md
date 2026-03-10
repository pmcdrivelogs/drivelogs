# Flask Drive Logs Application

A comprehensive vehicle log management system built with Flask and Tailwind CSS.

## Features

- User Authentication (Login/Logout)
- Super Admin Dashboard
- 13 Vehicle Management Modules
- Session Management
- Responsive Design

## Installation

1. Install Python 3.8 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Default Credentials

### User Login
- Email: `user@example.com`
- Password: `password123`

### Super Admin Login
- Username: `admin`
- Password: `admin123`

## Project Structure

```
Drive Logs/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── login.html
│   ├── super_admin_login.html
│   ├── home.html
│   └── admin_dashboard.html
├── static/               # Static files
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── img/              # Place your images here
│       ├── drive logs.png
│       ├── PMC LOGO.png
│       └── login  bus.png
└── README.md
```

## Image Setup

Place the following images in the `static/img/` folder:
- `drive logs.png` - Drive Logs logo
- `PMC LOGO.png` - College header logo
- `login  bus.png` - Bus image for login page

## Modules

1. Vehicle Profile
2. Trip Opening Attention Check List
3. Utilization Record
4. Fuel Consumption Statement
5. Daily Technical Remarks
6. Weekly/Forthnight Attention Checklist
7. Job Card
8. Monthly Periodical Maintenance
9. Halfyearly Periodical Maintenance
10. Annual Periodical Maintenance
11. Annual Summary & Recommendations
12. Incidents & Reports Record
13. Feedback

## Development

To run in development mode with auto-reload:
```bash
python app.py
```

## Security Note

⚠️ Change the `app.secret_key` in `app.py` before deploying to production!
⚠️ Replace dummy credentials with a proper database authentication system!

## Technologies Used

- Flask 3.0
- Tailwind CSS
- Jinja2 Templates
- Python 3.x
