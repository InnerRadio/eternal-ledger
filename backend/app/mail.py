from email.message import EmailMessage
import os
import smtplib


def get_mail_config():
    required = [
        "PURPAWS_SMTP_HOST",
        "PURPAWS_SMTP_PORT",
        "PURPAWS_SMTP_USERNAME",
        "PURPAWS_SMTP_PASSWORD",
        "PURPAWS_SMTP_FROM_EMAIL",
    ]

    missing = [key for key in required if not os.environ.get(key)]

    if missing:
        return {
            "ready": False,
            "missing": missing
        }

    return {
        "ready": True,
        "host": os.environ["PURPAWS_SMTP_HOST"],
        "port": int(os.environ["PURPAWS_SMTP_PORT"]),
        "username": os.environ["PURPAWS_SMTP_USERNAME"],
        "password": os.environ["PURPAWS_SMTP_PASSWORD"],
        "from_email": os.environ["PURPAWS_SMTP_FROM_EMAIL"],
        "from_name": os.environ.get("PURPAWS_SMTP_FROM_NAME", "PurPaws"),
        "use_tls": os.environ.get("PURPAWS_SMTP_USE_TLS", "1") == "1",
    }


def build_purpaws_verification_email(display_name, verify_url):
    safe_name = display_name or "there"

    subject = "Verify your PurPaws account"

    text_body = f"""Hi {safe_name},

Your PurPaws starter record has been saved.

Please verify your email to continue your setup:

{verify_url}

After verification, you will create your password, receive your Affiliate ID, and continue to your PurPaws Dashboard.

Protect. Remember. Rescue. Connect. Support.

PurPaws
"""

    html_body = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#060606;font-family:Inter,Arial,sans-serif;color:#F5F1EA;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#060606;padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="width:620px;max-width:92%;background:#F7F0FF;border-radius:22px;border:1px solid #E6DDF2;color:#24163E;overflow:hidden;">
            <tr>
              <td style="padding:34px 34px 18px;text-align:center;">
                <div style="font-size:12px;letter-spacing:.2em;font-weight:800;color:#6D35BE;text-transform:uppercase;">PurPaws Companion Network</div>
                <h1 style="margin:14px 0 8px;font-family:Georgia,serif;font-size:34px;font-weight:500;color:#24163E;">Verify your email</h1>
                <p style="margin:0;color:#6B6173;font-size:15px;line-height:1.6;">Your PurPaws starter record has been saved.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:10px 34px 26px;">
                <p style="font-size:15px;line-height:1.7;color:#3A2A4D;">Hi {safe_name},</p>
                <p style="font-size:15px;line-height:1.7;color:#3A2A4D;">Click below to verify your email and continue your account setup.</p>
                <p style="text-align:center;margin:28px 0;">
                  <a href="{verify_url}" style="display:inline-block;background:#6D35BE;color:#ffffff;text-decoration:none;padding:14px 24px;border-radius:10px;font-weight:800;">Verify Email & Continue</a>
                </p>
                <p style="font-size:13px;line-height:1.6;color:#6B6173;">After verification, you will create your password, receive your Affiliate ID, and continue to your PurPaws Dashboard.</p>
                <p style="font-size:12px;line-height:1.6;color:#6B6173;word-break:break-all;">If the button does not work, copy and paste this link:<br>{verify_url}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 34px 30px;border-top:1px solid #E6DDF2;text-align:center;color:#6B6173;font-size:12px;">
                Protect. Remember. Rescue. Connect. Support.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    return subject, text_body, html_body


def send_email(to_email, subject, text_body, html_body):
    config = get_mail_config()

    if not config["ready"]:
        return {
            "sent": False,
            "reason": "missing_smtp_config",
            "missing": config["missing"]
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f'{config["from_name"]} <{config["from_email"]}>'
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    if config["use_tls"]:
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(config["host"], config["port"]) as server:
            server.login(config["username"], config["password"])
            server.send_message(msg)

    return {
        "sent": True,
        "to": to_email
    }


def send_onboarding_verification_email(to_email, display_name, verify_url):
    subject, text_body, html_body = build_purpaws_verification_email(
        display_name=display_name,
        verify_url=verify_url
    )

    return send_email(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body
    )
