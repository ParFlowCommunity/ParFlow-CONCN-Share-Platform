"""Existing SMTP email-action delivery and token issuance."""

from datetime import timedelta
from email.message import EmailMessage
import os
import secrets
import smtplib
import ssl
from flask import current_app
from ..common import ApiError, now, digest
from ..repositories.db import transaction, one


def issue_email_action(user_id, address, purpose):
    if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
        raise ApiError("EMAIL_SERVICE_UNAVAILABLE", 503)
    token = secrets.token_urlsafe(32)
    with transaction() as c:
        one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (user_id,))
        c.execute(
            "UPDATE email_actions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s AND purpose=%s AND consumed_at IS NULL",
            (user_id, purpose),
        )
        c.execute(
            "INSERT INTO email_actions(user_id,purpose,target_email,token_hash,expires_at) VALUES(%s,%s,%s,%s,%s)",
            (user_id, purpose, address, digest(token), now() + timedelta(minutes=30)),
        )
    link = current_app.config["PUBLIC_URL"] + "/account?email_token=" + token
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = address
    msg["Subject"] = "ParFlow CONCN Share Platform · 邮箱操作 / Email action"
    msg.set_content(
        "请在 30 分钟内打开链接完成操作。如非本人申请，请忽略。\nOpen within 30 minutes. Ignore if you did not request this.\n"
        + link
    )
    try:
        with smtplib.SMTP(
            os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15
        ) as server:
            server.starttls(context=ssl.create_default_context())
            if os.getenv("SMTP_USERNAME"):
                server.login(
                    os.environ["SMTP_USERNAME"], os.getenv("SMTP_PASSWORD", "")
                )
            server.send_message(msg)
    except Exception:
        with transaction() as c:
            c.execute(
                "UPDATE email_actions SET revoked_at=UTC_TIMESTAMP(6) WHERE token_hash=%s",
                (digest(token),),
            )
        raise ApiError("EMAIL_SERVICE_UNAVAILABLE", 503)
