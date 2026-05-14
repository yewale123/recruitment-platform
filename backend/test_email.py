"""Quick test — run from backend/ to verify Gmail SMTP works."""
import os
from dotenv import load_dotenv
load_dotenv()

gmail_user = os.getenv("GMAIL_USER", "").strip()
app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()
sender_name = os.getenv("GMAIL_SENDER_NAME", "Test").strip()

print(f"GMAIL_USER     = '{gmail_user}'")
print(f"APP_PASSWORD   = '{app_password[:4]}...{app_password[-4:]}' (len={len(app_password)})")
print()

if not gmail_user or not app_password:
    print("ERROR: credentials missing in .env")
    exit(1)

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

TO = gmail_user  # send to yourself as a test

msg = MIMEMultipart()
msg["Subject"] = "Test — Recruitment Platform Email"
msg["From"] = f"{sender_name} <{gmail_user}>"
msg["To"] = TO
msg.attach(MIMEText("This is a test email from your recruitment platform.", "plain"))

try:
    print(f"Connecting to smtp.gmail.com:465 ...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
        print("Logging in ...")
        smtp.login(gmail_user, app_password)
        print("Sending ...")
        smtp.sendmail(gmail_user, TO, msg.as_string())
    print(f"\nSUCCESS — email sent to {TO}")
except Exception as e:
    print(f"\nFAILED: {e}")
