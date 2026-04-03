"""
EmailPoller — IMAP polling logic for email_imap schedule triggers.

Connects to an IMAP server, searches for matching emails, and yields
metadata dicts for each new (unseen) matching message.

This module is pure logic — no DB access, no Celery calls.
The caller (poll_email_triggers task) handles deduplication and firing.

Supported filters (all optional):
  filter_sender      — FROM contains this string
  filter_subject     — SUBJECT contains this string
  filter_body        — body text contains this string (fetched only when set)
  unread_only        — only UNSEEN messages (default True)
  has_attachment     — only messages with attachments
  attachment_extensions — list of extensions like [".pdf", ".csv"]
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
import ssl
from email.header import decode_header
from typing import Generator

log = logging.getLogger("triggers.email_poller")


# ── Header decoding helpers ───────────────────────────────────────────────────

def _decode_header_value(raw: str | bytes | None) -> str:
    """Decode an RFC-2047 encoded email header to a plain string."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def _get_body_text(msg: email.message.Message) -> str:
    """Extract plain-text body from a (possibly multipart) email."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(body_parts)


def _has_attachment(msg: email.message.Message) -> bool:
    """Return True if the message has at least one attachment."""
    if msg.is_multipart():
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                return True
    return False


def _attachment_extensions(msg: email.message.Message) -> list[str]:
    """Return list of lowercase file extensions for all attachments."""
    exts = []
    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                name = _decode_header_value(filename)
                dot = name.rfind(".")
                if dot != -1:
                    exts.append(name[dot:].lower())
    return exts


# ── IMAP search criteria builder ──────────────────────────────────────────────

def _build_search_criteria(config: dict) -> str:
    """
    Build an IMAP SEARCH criteria string from the trigger config.
    We keep server-side filtering minimal (UNSEEN + FROM/SUBJECT when set)
    and do the rest client-side to avoid IMAP dialect issues.
    """
    parts = []

    if config.get("unread_only", True):
        parts.append("UNSEEN")

    sender = (config.get("filter_sender") or "").strip()
    if sender:
        # IMAP FROM search is substring-based on most servers
        safe = sender.replace('"', "")
        parts.append(f'FROM "{safe}"')

    subject = (config.get("filter_subject") or "").strip()
    if subject:
        safe = subject.replace('"', "")
        parts.append(f'SUBJECT "{safe}"')

    return " ".join(parts) if parts else "ALL"


# ── Main poller ───────────────────────────────────────────────────────────────

def poll_mailbox(config: dict) -> Generator[dict, None, None]:
    """
    Connect to IMAP, search for matching messages, yield metadata dicts.

    Each yielded dict:
      {
        "uid":     "12345",
        "sender":  "alice@example.com",
        "subject": "Invoice #42",
        "date":    "Thu, 02 Apr 2026 ...",
        "has_attachment": True,
        "attachment_extensions": [".pdf"],
      }

    Raises on connection/auth failure so the caller can log it.
    """
    host     = config.get("host", "").strip()
    port     = int(config.get("port", 993))
    username = config.get("username", "").strip()
    password = config.get("password", "")   # already decrypted by caller
    mailbox  = config.get("mailbox", "INBOX").strip() or "INBOX"
    use_ssl  = config.get("use_ssl", True)

    # ── Connect ───────────────────────────────────────────────────────────────
    if use_ssl:
        ctx = ssl.create_default_context()
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
    else:
        conn = imaplib.IMAP4(host, port)
        conn.starttls()

    try:
        conn.login(username, password)
        # readonly=True — don't auto-mark messages as SEEN just by fetching them.
        # The dedup table (EmailTriggerState) is the source of truth for what's processed.
        conn.select(mailbox, readonly=True)

        criteria = _build_search_criteria(config)
        log.debug(f"[email_poller] SEARCH {criteria} on {host}/{mailbox}")

        status, data = conn.uid("SEARCH", None, criteria)
        if status != "OK" or not data or not data[0]:
            return

        uids = data[0].split()
        log.debug(f"[email_poller] found {len(uids)} candidate(s)")

        # Client-side filters that IMAP SEARCH can't reliably handle
        filter_body       = (config.get("filter_body") or "").strip().lower()
        need_attachment   = config.get("has_attachment", False)
        allowed_exts      = [
            e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in (config.get("attachment_extensions") or [])
        ]

        for uid_bytes in uids:
            uid = uid_bytes.decode()

            # Always fetch full RFC822 — more reliable across IMAP servers
            # (RFC822.HEADER can miss headers on some Gmail configurations)
            status2, msg_data = conn.uid("FETCH", uid, "(RFC822)")
            if status2 != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
            if not raw:
                continue

            msg = email.message_from_bytes(raw)

            sender  = _decode_header_value(msg.get("From", ""))
            subject = _decode_header_value(msg.get("Subject", ""))
            date    = msg.get("Date", "")

            # ── Client-side filter: body ──────────────────────────────────────
            if filter_body:
                body = _get_body_text(msg).lower()
                if filter_body not in body:
                    log.debug(f"[email_poller] uid={uid} rejected: body filter")
                    continue

            # ── Client-side filter: attachment presence ───────────────────────
            att_exts = _attachment_extensions(msg)
            has_att  = bool(att_exts) or _has_attachment(msg)

            if need_attachment and not has_att:
                log.debug(f"[email_poller] uid={uid} rejected: no attachment")
                continue

            if allowed_exts:
                if not any(e in att_exts for e in allowed_exts):
                    log.debug(f"[email_poller] uid={uid} rejected: attachment ext mismatch")
                    continue

            yield {
                "uid":                   uid,
                "sender":                sender,
                "subject":               subject,
                "date":                  date,
                "has_attachment":        has_att,
                "attachment_extensions": att_exts,
            }

    finally:
        try:
            conn.logout()
        except Exception:
            pass
