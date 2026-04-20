"""MIME parsing to LLM-friendly markdown."""

import email
import email.policy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage

from bs4 import BeautifulSoup
from markdownify import markdownify


@dataclass
class AttachmentInfo:
    filename: str
    content_type: str
    data: bytes
    size: int


@dataclass
class ParsedEmail:
    message_id: str
    gmail_id: str
    from_addr: str
    to_addrs: list[str]
    cc_addrs: list[str]
    bcc_addrs: list[str]
    date: datetime | None
    subject: str
    labels: list[str]
    body_markdown: str
    body_plain: str
    attachments: list[AttachmentInfo] = field(default_factory=list)


def parse_raw_email(raw_mime: bytes, gmail_id: str, labels: list[str]) -> ParsedEmail:
    """Parse raw MIME bytes into a structured ParsedEmail."""
    msg = email.message_from_bytes(raw_mime, policy=email.policy.default)

    message_id = msg.get("Message-ID", "") or ""
    from_addr = _decode_header(msg.get("From", ""))
    to_addrs = _parse_address_list(msg.get("To", ""))
    cc_addrs = _parse_address_list(msg.get("Cc", ""))
    bcc_addrs = _parse_address_list(msg.get("Bcc", ""))
    subject = _decode_header(msg.get("Subject", "(no subject)"))
    date = _parse_date(msg.get("Date", ""))

    body_plain, body_html = _extract_body(msg)
    attachments = _extract_attachments(msg)

    # Convert body to markdown
    if body_html:
        body_markdown = _html_to_markdown(body_html)
    elif body_plain:
        body_markdown = body_plain
    else:
        body_markdown = "(empty message body)"

    return ParsedEmail(
        message_id=message_id,
        gmail_id=gmail_id,
        from_addr=from_addr,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        bcc_addrs=bcc_addrs,
        date=date,
        subject=subject,
        labels=labels,
        body_markdown=body_markdown,
        body_plain=body_plain or body_markdown,
        attachments=attachments,
    )


def _decode_header(value: str) -> str:
    """Decode an email header value."""
    if not value:
        return ""
    return str(value).strip()


def _parse_address_list(value: str) -> list[str]:
    """Parse a comma-separated address list."""
    if not value:
        return []
    return [addr.strip() for addr in str(value).split(",") if addr.strip()]


def _parse_date(date_str: str) -> datetime | None:
    """Parse email date header."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(str(date_str))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _extract_body(msg: EmailMessage) -> tuple[str, str]:
    """Extract plain text and HTML body from a MIME message."""
    body_plain = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                continue

            if content_type == "text/plain" and not body_plain:
                payload = part.get_content()
                if isinstance(payload, str):
                    body_plain = payload
                elif isinstance(payload, bytes):
                    body_plain = payload.decode("utf-8", errors="replace")

            elif content_type == "text/html" and not body_html:
                payload = part.get_content()
                if isinstance(payload, str):
                    body_html = payload
                elif isinstance(payload, bytes):
                    body_html = payload.decode("utf-8", errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_content()
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")
        if isinstance(payload, str):
            if content_type == "text/html":
                body_html = payload
            else:
                body_plain = payload

    return body_plain, body_html


def _extract_attachments(msg: EmailMessage) -> list[AttachmentInfo]:
    """Extract all attachments from a MIME message."""
    attachments = []

    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        content_type = part.get_content_type()

        # Skip text body parts
        if content_type in ("text/plain", "text/html") and "attachment" not in disposition:
            continue

        filename = part.get_filename()
        if not filename and "attachment" not in disposition:
            continue

        if not filename:
            ext = _guess_extension(content_type)
            filename = f"attachment{ext}"

        try:
            data = part.get_content()
            if isinstance(data, str):
                data = data.encode("utf-8")
            elif not isinstance(data, bytes):
                # For EmailMessage objects (nested emails)
                data = bytes(part)
        except Exception:
            continue

        attachments.append(AttachmentInfo(
            filename=_sanitize_filename(filename),
            content_type=content_type,
            data=data,
            size=len(data),
        ))

    return attachments


def _html_to_markdown(html: str) -> str:
    """Convert HTML email body to clean markdown."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove style and script tags
    for tag in soup.find_all(["style", "script", "head"]):
        tag.decompose()

    md = markdownify(str(soup), heading_style="ATX", strip=["img"])

    # Clean up excessive whitespace
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r" {2,}", " ", md)
    return md.strip()


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename for filesystem safety."""
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    filename = filename.strip(". ")
    return filename or "attachment"


def _guess_extension(content_type: str) -> str:
    """Guess file extension from content type."""
    mapping = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "application/zip": ".zip",
        "text/csv": ".csv",
    }
    return mapping.get(content_type, ".bin")
