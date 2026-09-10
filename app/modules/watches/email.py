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


IMAGES_PUBLIQUES = "https://app.axial-ia.fr/api/viz"


def _tableau_html(cellules: list[list[str]]) -> str:
    if not cellules:
        return ""
    tete = "".join(f'<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #d9d7e8">'
                   f"{_inline(c)}</th>" for c in cellules[0])
    corps = "".join("<tr>" + "".join(f'<td style="padding:6px 8px;border-bottom:1px solid #eee">{_inline(c)}</td>'
                                     for c in ligne) + "</tr>" for ligne in cellules[1:])
    return f'<table style="border-collapse:collapse;width:100%;font-size:13px"><thead><tr>{tete}</tr></thead>' \
           f"<tbody>{corps}</tbody></table>"


def _md_to_html(md: str, vizs: list[dict] | None = None) -> str:
    """Minimal markdown → HTML for the digest (headings, bold, bullets, rules,
    tables, and ```viz blocks as hosted images — a mail client never runs a
    script, an image is the only form a chart can take there)."""
    out: list[str] = []
    bullets: list[str] = []
    par_index = {v["index"]: v for v in (vizs or []) if isinstance(v, dict)}
    lignes = md.splitlines()

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    i, k = 0, 0
    while i < len(lignes):
        line = lignes[i].rstrip()
        if not line.strip():
            flush()
            i += 1
            continue
        if line.strip().startswith("```viz"):
            flush()
            j = i + 1
            while j < len(lignes) and not lignes[j].strip().startswith("```"):
                j += 1
            v = par_index.get(k)
            k += 1
            if v and v.get("statut") == "ok" and v.get("empreinte"):
                titre = html.escape((v.get("spec") or {}).get("title") or "")
                out.append(f'<p style="margin:14px 0"><img src="{IMAGES_PUBLIQUES}/{v["empreinte"]}.png" '
                           f'width="560" alt="{titre}" style="max-width:100%;height:auto;border:1px solid #e4e2f0;'
                           f'border-radius:8px"></p>')
            elif v:
                from app.modules.viz.pipeline import tableau_de_repli

                out.append(_tableau_html(tableau_de_repli(v.get("spec") or {})))
            i = j + 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lignes) \
                and re.match(r"^\|?\s*:?-{3,}", lignes[i + 1].strip()):
            flush()
            cellules = []
            j = i
            while j < len(lignes) and lignes[j].strip().startswith("|"):
                if j != i + 1:
                    cellules.append([c.strip() for c in lignes[j].strip().strip("|").split("|")])
                j += 1
            out.append(_tableau_html(cellules))
            i = j
            continue
        i += 1
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
        '<p style="color:#8888a0;font-size:12px">Envoyé par ton agent de veille Axial.</p>'
        "</div>"
    )


def _send_via_resend(recipients: list[str], subject: str, body: str,
                     vizs: list[dict] | None = None) -> bool:
    """Send through Resend's HTTP API (preferred path)."""
    import httpx

    settings = get_settings()
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}",
                     "Content-Type": "application/json"},
            json={"from": settings.mail_from, "to": recipients, "subject": subject,
                  "html": _md_to_html(body, vizs), "text": body},
            timeout=20.0,
        )
        if r.status_code >= 300:
            logger.warning("Resend send failed (%s): %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception:
        logger.warning("Resend send failed", exc_info=True)
        return False


def send_email(recipients: list[str], subject: str, body: str,
               vizs: list[dict] | None = None) -> bool:
    """Send the digest (markdown `body`) as HTML + plain-text. Prefers the Resend
    HTTP API; falls back to SMTP. Returns False (logged) if unconfigured/failed."""
    settings = get_settings()
    if not recipients:
        logger.info("No recipients; skipping email.")
        return False
    if settings.resend_api_key:
        return _send_via_resend(recipients, subject, body, vizs)
    if not settings.smtp_host:
        logger.info("No email provider configured (Resend/SMTP); skipping.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(_md_to_html(body, vizs), "html", "utf-8"))
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
