SMTP setup and troubleshooting
===============================

Follow these steps to fix Gmail SMTP authentication (535 BadCredentials) and test email sending.

1) Use an App Password (recommended)
   - Ensure the Gmail account (`SMTP_USER` in your `.env`) has 2-Step Verification enabled.
   - In Google Account > Security > "App passwords" create a new App Password for "Mail" and "Other (Custom name)" (e.g. DriveLogs).
   - Copy the 16-character password and set it as `SMTP_PASSWORD` in your `.env`.

2) `.env` keys you should have (example):

   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your.email@gmail.com
   SMTP_PASSWORD=your_16_char_app_password
   EMAIL_FROM=your.email@gmail.com
   EMAIL_TO=recipient1@example.com,recipient2@example.com

3) Alternative options if Gmail is unsuitable
   - Use a transactional email provider (SendGrid, Mailgun, Postmark) and put their SMTP creds into the same `.env` keys.
   - Or use a service-specific API client (recommended for production), e.g., SendGrid Python SDK.

4) Test sending
   - After updating `.env`, run:

     python send_test_email.py

   - Expected output: `Email sent: True` and a confirmation in the recipient inbox.

5) Common issues & notes
   - "535 BadCredentials" means the SMTP server rejected the username/password. Confirm the `SMTP_USER` exactly matches the account and `SMTP_PASSWORD` is an App Password (if using Gmail).
   - If you changed the password, restart your app / reload environment so `dotenv` picks up the new value.
   - For Gmail with port 587 the code starts TLS (STARTTLS). Port 465 uses SSL/TLS directly — both are supported by `email_helper.py`.

If you want, paste a new `SMTP_PASSWORD` here and I can update your `.env` file for you (I will not store it beyond this workspace edit). Otherwise follow these steps and re-run `python send_test_email.py`.
