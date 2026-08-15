"""Professional-email gate.

Registration is restricted to professional email domains unless ALLOW_FREEMAIL
is set. Ported verbatim from the legacy platform to preserve behaviour.
"""
from __future__ import annotations

FREEMAIL_DOMAINS: frozenset[str] = frozenset({
    # Anglophone
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.fr", "yahoo.co.uk", "ymail.com",
    "outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr",
    "live.com", "live.fr", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "gmx.com", "gmx.fr", "gmx.net", "mail.com",
    # Privacy-focused
    "protonmail.com", "proton.me", "tutanota.com", "tutamail.com",
    # French ISPs
    "orange.fr", "wanadoo.fr", "laposte.net", "free.fr", "sfr.fr",
    "bbox.fr", "numericable.fr", "neuf.fr", "club-internet.fr",
    # Disposable (defence in depth)
    "mailinator.com", "10minutemail.com", "tempmail.com",
    "throwaway.email", "guerrillamail.com", "yopmail.com",
})


def is_professional_email(email: str) -> bool:
    """True if the email domain is NOT a known freemail/disposable domain."""
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].lower().strip()
    return domain not in FREEMAIL_DOMAINS
