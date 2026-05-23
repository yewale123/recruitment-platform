"""
Gmail SMTP email sender for candidate outreach.
Uses App Password — no OAuth needed.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

settings = get_settings()


def send_outreach_email(
    to_email: str,
    candidate_name: str,
    job_title: str,
    skills: list[str],
) -> bool:
    """
    Send a personalized outreach email to a candidate.
    Returns True if sent successfully, False otherwise.
    """
    gmail_user = settings.GMAIL_USER.strip()
    app_password = settings.GMAIL_APP_PASSWORD.strip()
    sender_name = settings.GMAIL_SENDER_NAME.strip() or "Recruitment Team"

    if not gmail_user or not app_password:
        print("[Email] Gmail not configured — skipping send")
        return False

    # Demo mode — redirect all emails to DEMO_EMAIL if set
    demo_email = getattr(settings, "DEMO_EMAIL", "").strip()
    if demo_email:
        to_email = demo_email

    first_name = candidate_name.split()[0].capitalize() if candidate_name else "there"
    skill1 = skills[0] if len(skills) > 0 else ""
    skill2 = skills[1] if len(skills) > 1 else ""

    skills_line = ""
    if skill1 and skill2:
        skills_line = f"Your expertise in {skill1} and {skill2} is exactly what we're looking for.\n\n"
    elif skill1:
        skills_line = f"Your expertise in {skill1} is exactly what we're looking for.\n\n"

    subject = f"Exciting Opportunity — {job_title} Role"

    body = f"""Hi {first_name},

I came across your profile and believe you'd be an excellent fit for our {job_title} position.

{skills_line}Would you be open to sharing your updated resume? I'd love to discuss this opportunity with you in more detail.

Looking forward to hearing from you.

Best regards,
{sender_name}"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{gmail_user}>"
        msg["To"] = to_email

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(gmail_user, app_password)
            smtp.sendmail(gmail_user, to_email, msg.as_string())

        print(f"[Email] Sent to {to_email} ({candidate_name})")
        return True

    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {e}")
        return False
