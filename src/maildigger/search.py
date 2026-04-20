"""Gmail search query building."""

from datetime import datetime


def build_query(
    raw_query: str | None = None,
    persons: list[str] | None = None,
    senders: list[str] | None = None,
    recipients: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    subject: str | None = None,
    has_attachment: bool = False,
    labels: list[str] | None = None,
) -> str:
    """Build a Gmail search query string.

    Two modes:
    - Raw: pass a Gmail query string directly (same syntax as Gmail search bar)
    - Structured: build from individual parameters

    The `persons` parameter matches emails both FROM and TO each address.
    """
    if raw_query:
        return raw_query

    parts = []

    # Persons: match both sent and received
    if persons:
        person_clauses = []
        for person in persons:
            person_clauses.append(f"(from:{person} OR to:{person})")
        if len(person_clauses) == 1:
            parts.append(person_clauses[0])
        else:
            parts.append("(" + " OR ".join(person_clauses) + ")")

    # Explicit senders
    if senders:
        if len(senders) == 1:
            parts.append(f"from:{senders[0]}")
        else:
            parts.append("(" + " OR ".join(f"from:{s}" for s in senders) + ")")

    # Explicit recipients
    if recipients:
        if len(recipients) == 1:
            parts.append(f"to:{recipients[0]}")
        else:
            parts.append("(" + " OR ".join(f"to:{r}" for r in recipients) + ")")

    # Date range
    if after:
        parts.append(f"after:{_normalize_date(after)}")
    if before:
        parts.append(f"before:{_normalize_date(before)}")

    # Subject
    if subject:
        parts.append(f"subject:({subject})")

    # Attachments
    if has_attachment:
        parts.append("has:attachment")

    # Labels
    if labels:
        for label in labels:
            parts.append(f"label:{label}")

    if not parts:
        raise ValueError("No search criteria provided. Use --query or specify filters.")

    return " ".join(parts)


def _normalize_date(date_str: str) -> str:
    """Convert date string to Gmail format YYYY/MM/DD."""
    # Already in Gmail format
    if "/" in date_str and len(date_str) == 10:
        return date_str

    # ISO format YYYY-MM-DD
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y/%m/%d")
    except ValueError:
        pass

    # Try other common formats
    for fmt in ("%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y/%m/%d")
        except ValueError:
            continue

    raise ValueError(
        f"Cannot parse date '{date_str}'. Use YYYY-MM-DD format."
    )
