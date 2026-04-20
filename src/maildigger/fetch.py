"""Email fetching via IMAP with Gmail's X-GM-RAW search extension."""

import email as email_lib
import imaplib
from dataclasses import dataclass, field

from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn,
)


@dataclass
class RawEmail:
    uid: str
    raw_mime: bytes
    gmail_labels: list[str] = field(default_factory=list)


def fetch_message_uids(
    imap: imaplib.IMAP4_SSL,
    query: str,
    limit: int | None = None,
) -> list[bytes]:
    """Search Gmail via IMAP using X-GM-RAW for native Gmail query syntax."""
    imap.select('"[Gmail]/All Mail"', readonly=True)

    # X-GM-RAW allows full Gmail search syntax over IMAP
    status, data = imap.uid("SEARCH", None, f'X-GM-RAW "{_escape_query(query)}"')

    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status} {data}")

    uids = data[0].split() if data[0] else []

    # Gmail returns oldest-first; reverse so newest-first, then apply limit
    uids.reverse()
    if limit:
        uids = uids[:limit]

    return uids


def fetch_messages(
    imap: imaplib.IMAP4_SSL,
    uids: list[bytes],
    batch_size: int = 50,
) -> list[RawEmail]:
    """Fetch full MIME messages by UID in batches."""
    results = []
    total = len(uids)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task("Downloading emails...", total=total)

        for i in range(0, total, batch_size):
            batch_uids = uids[i : i + batch_size]
            uid_str = b",".join(batch_uids)

            # Fetch RFC822 (full MIME) and X-GM-LABELS in one call
            status, data = imap.uid(
                "FETCH", uid_str, "(RFC822 X-GM-LABELS)"
            )

            if status != "OK":
                progress.console.print(
                    f"[yellow]Warning: Batch fetch failed: {status}[/yellow]"
                )
                progress.update(task, advance=len(batch_uids))
                continue

            # Parse the response — data contains alternating metadata and content
            j = 0
            while j < len(data):
                item = data[j]
                if isinstance(item, tuple) and len(item) == 2:
                    header_line = item[0].decode("utf-8", errors="replace")
                    raw_mime = item[1]

                    # Extract UID from header
                    uid = _extract_uid(header_line)
                    labels = _extract_labels(header_line)

                    results.append(RawEmail(
                        uid=uid,
                        raw_mime=raw_mime,
                        gmail_labels=labels,
                    ))
                j += 1

            progress.update(task, advance=len(batch_uids))

    return results


def count_messages(imap: imaplib.IMAP4_SSL, query: str) -> int:
    """Count messages matching a query."""
    imap.select('"[Gmail]/All Mail"', readonly=True)
    status, data = imap.uid("SEARCH", None, f'X-GM-RAW "{_escape_query(query)}"')
    if status != "OK":
        return 0
    uids = data[0].split() if data[0] else []
    return len(uids)


def _escape_query(query: str) -> str:
    """Escape double quotes in the query for IMAP X-GM-RAW."""
    return query.replace("\\", "\\\\").replace('"', '\\"')


def _extract_uid(header: str) -> str:
    """Extract UID from IMAP FETCH response header."""
    # Header looks like: '1234 (UID 5678 X-GM-LABELS (...) RFC822 {12345}'
    import re
    match = re.search(r"UID\s+(\d+)", header)
    return match.group(1) if match else "unknown"


def _extract_labels(header: str) -> list[str]:
    """Extract Gmail labels from IMAP FETCH response header."""
    import re
    match = re.search(r'X-GM-LABELS\s+\(([^)]*)\)', header)
    if not match:
        return []
    raw = match.group(1)
    # Labels can be quoted or unquoted
    labels = re.findall(r'"([^"]+)"|(\S+)', raw)
    return [quoted or unquoted for quoted, unquoted in labels if quoted or unquoted]
