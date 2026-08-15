"""SMTP email sender for veille digests — best-effort, degrades when unconfigured.

Sends a multipart email: a readable HTML rendering of the markdown digest, with a
plain-text fallback. Never raises to the caller — a failed send is logged and the
run still succeeds.
"""
from __future__ import annotations

import html
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger("axial.watches.email")


def _inline(text: str) -> str:
    text = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def _md_to_html(md: str) -> str:
    """Minimal markdown → HTML for the digest (headings, bold, bullets, rules)."""
    out: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if line.startswith("### "):
            flush()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush()
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.strip() in ("---", "***"):
            flush()
            out.append("<hr>")
        elif line.lstrip().startswith(("- ", "* ")):
            bullets.append(line.lstrip()[2:])
        else:
            flush()
            out.append(f"<p>{_inline(line)}</p>")
    flush()
    body = "\n".join(out)
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:680px;'
        'margin:0 auto;color:#1a1a2e;line-height:1.55;font-size:14px">'
        f"{body}"
        '<hr style="margin-top:28px;border:none;border-top:1px solid #e5e5ef">'
        '<p style="color:#8888a0;font-size:12px">Envoyé par votre agent de veille Axial.</p>'
        "</div>"
    )


def _send_via_resend(recipients: list[str], subject: str, body: str) -> bool:
    """Send through Resend's HTTP API (preferred path)."""
    import httpx

    settings = get_settings()
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}",
                     "Content-Type": "application/json"},
            json={"from": settings.mail_from, "to": recipients, "subject": subject,
                  "html": _md_to_html(body), "text": body},
            timeout=20.0,
        )
        if r.status_code >= 300:
            logger.warning("Resend send failed (%s): %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception:
        logger.warning("Resend send failed", exc_info=True)
        return False


def send_email(recipients: list[str], subject: str, body: str) -> bool:
    """Send the digest (markdown `body`) as HTML + plain-text. Prefers the Resend
    HTTP API; falls back to SMTP. Returns False (logged) if unconfigured/failed."""
    settings = get_settings()
    if not recipients:
        logger.info("No recipients; skipping email.")
        return False
    if settings.resend_api_key:
        return _send_via_resend(recipients, subject, body)
    if not settings.smtp_host:
        logger.info("No email provider configured (Resend/SMTP); skipping.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(_md_to_html(body), "html", "utf-8"))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, recipients, msg.as_string())
        return True
    except Exception:
        logger.warning("Email send failed", exc_info=True)
        return False
