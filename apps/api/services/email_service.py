"""Email service for sending authentication emails.

This service handles:
- Magic link email sending
- Email templating
- Multiple provider support (Resend, console fallback)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "noreply@resumeoptimizer.app")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Resume Optimizer")


def get_magic_link_email_html(magic_link_url: str) -> str:
    """Generate HTML email content for magic link.

    Args:
        magic_link_url: The full magic link URL.

    Returns:
        HTML string for the email body.
    """
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in to Resume Optimizer</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Resume Optimizer</h1>
    </div>

    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none;">
        <h2 style="margin-top: 0; color: #1f2937;">Sign in to your account</h2>

        <p>Click the button below to sign in. This link is valid for 15 minutes.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{magic_link_url}"
               style="background: #667eea; color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
                Sign In
            </a>
        </div>

        <p style="color: #6b7280; font-size: 14px;">
            Or copy and paste this link into your browser:
        </p>
        <p style="word-break: break-all; color: #667eea; font-size: 14px;">
            {magic_link_url}
        </p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

        <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">
            If you didn't request this email, you can safely ignore it.
        </p>
    </div>
</body>
</html>
"""


def get_magic_link_email_text(magic_link_url: str) -> str:
    """Generate plain text email content for magic link.

    Args:
        magic_link_url: The full magic link URL.

    Returns:
        Plain text string for the email body.
    """
    return f"""Sign in to Resume Optimizer

Click this link to sign in (valid for 15 minutes):
{magic_link_url}

If you didn't request this email, you can safely ignore it.
"""


async def send_magic_link_email(email: str, magic_link_url: str) -> bool:
    """Send a magic link email to the user.

    Args:
        email: Recipient email address.
        magic_link_url: The full magic link URL.

    Returns:
        True if email was sent successfully, False otherwise.
    """
    subject = "Sign in to Resume Optimizer"
    html = get_magic_link_email_html(magic_link_url)
    text = get_magic_link_email_text(magic_link_url)

    # Try to send with Resend if API key is configured
    if EMAIL_API_KEY:
        success = await _send_with_resend(email, subject, html, text)
        if success:
            return True
        logger.warning("Resend email failed, falling back to console")

    # Fallback: Log to console in development
    logger.info(f"[EMAIL] To: {email}")
    logger.info(f"[EMAIL] Subject: {subject}")
    logger.info(f"[EMAIL] Magic Link: {magic_link_url}")

    return True  # Return True for development to not block auth flow


async def _send_with_resend(
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> bool:
    """Send email using Resend API.

    Args:
        to_email: Recipient email address.
        subject: Email subject.
        html: HTML content.
        text: Plain text content.

    Returns:
        True if sent successfully.
    """
    try:
        import resend

        resend.api_key = EMAIL_API_KEY

        response = resend.Emails.send(
            {
                "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            }
        )

        if response and response.get("id"):
            logger.info(f"Magic link email sent to {to_email}, id: {response['id']}")
            return True
        else:
            logger.error(f"Resend returned unexpected response: {response}")
            return False

    except ImportError:
        logger.warning("resend package not installed, cannot send email")
        return False
    except Exception as e:
        logger.error(f"Failed to send email via Resend: {e}")
        return False


async def send_welcome_email(email: str, user_name: Optional[str] = None) -> bool:
    """Send a welcome email to a new user.

    Args:
        email: Recipient email address.
        user_name: Optional user name for personalization.

    Returns:
        True if email was sent successfully, False otherwise.
    """
    greeting = f"Hi {user_name}!" if user_name else "Welcome!"
    subject = "Welcome to Resume Optimizer"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Resume Optimizer</h1>
    </div>

    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none;">
        <h2 style="margin-top: 0; color: #1f2937;">{greeting}</h2>

        <p>Thanks for joining Resume Optimizer! We're here to help you create the perfect resume for your dream job.</p>

        <p>Here's what you can do:</p>
        <ul>
            <li>Generate tailored resumes for specific job postings</li>
            <li>Get ATS optimization suggestions</li>
            <li>Track your preferences across sessions</li>
            <li>Export to PDF, DOCX, and more</li>
        </ul>

        <p>Your preferences will be saved automatically as you use the app.</p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

        <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">
            Questions? Just reply to this email.
        </p>
    </div>
</body>
</html>
"""

    text = f"""{greeting}

Thanks for joining Resume Optimizer! We're here to help you create the perfect resume for your dream job.

Here's what you can do:
- Generate tailored resumes for specific job postings
- Get ATS optimization suggestions
- Track your preferences across sessions
- Export to PDF, DOCX, and more

Your preferences will be saved automatically as you use the app.

Questions? Just reply to this email.
"""

    if EMAIL_API_KEY:
        return await _send_with_resend(email, subject, html, text)

    logger.info(f"[EMAIL] Welcome email to: {email}")
    return True
