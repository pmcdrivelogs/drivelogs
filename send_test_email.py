"""Send a quick test email using the configured SMTP settings in .env.

Usage:
  python send_test_email.py
"""
from dotenv import load_dotenv
load_dotenv()

from email_helper import send_email

def main():
    ok = send_email('Drive Logs - Test Email', 'This is a test email from Drive Logs reminders setup.')
    print('Email sent:', ok)

if __name__ == '__main__':
    main()
