import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings as settings_email


def send_email(to: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings_email.smtp_from_email
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    if not settings_email.smtp_host:
        print(f"[EMAIL] To: {to}, Subject: {subject}")
        print(msg.as_string())
        return

    with smtplib.SMTP(settings_email.smtp_host, settings_email.smtp_port) as server:
        server.starttls()
        server.login(settings_email.smtp_user, settings_email.smtp_password)
        server.sendmail(settings_email.smtp_from_email, to, msg.as_string())

def send_verification_email(to_email: str, token: str):
    subject = "Azens Email Verification"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Verify your email</h2>
        <p>Click the button below to verify your email address.</p>
        <a href="{settings_email.frontend_url}/auth/verify?token={token}"
        style="display:inline-block; padding:12px 24px; background:#0E1E35;
                color:#fff; border-radius:999px; text-decoration:none;
                font-weight:600;">
        Verify email
        </a>
        <p style="color:#999; font-size:13px; margin-top:24px;">
        If you didn't create an account, you can ignore this email.
        </p>
    </div>
    """

    send_email(to=to_email, subject=subject, html_body=html_body)


def send_password_reset_email(to_email: str, token: str):
    subject = "Azens Password Reset"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
        <h2>Reset your password</h2>
        <p>Click the button below to set a new password. This link expires in 1 hour.</p>
        <a href="{settings_email.frontend_url}/auth/reset-password?token={token}"
        style="display:inline-block; padding:12px 24px; background:#0E1E35;
                color:#fff; border-radius:999px; text-decoration:none;
                font-weight:600;">
        Reset password
        </a>
        <p style="color:#999; font-size:13px; margin-top:24px;">
        If you didn't request a password reset, you can ignore this email.
        </p>
    </div>
    """

    send_email(to=to_email, subject=subject, html_body=html_body)
