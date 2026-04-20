"""Output directory structure, email rendering, and manifest generation."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .attachments import save_and_convert
from .parse import ParsedEmail


def create_output_dir(base_path: str, query: str) -> Path:
    """Create a timestamped output directory."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = _slugify(query)[:60]
    dir_name = f"{timestamp}_{slug}"
    out_dir = Path(base_path) / dir_name / "emails"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir.parent


def write_email(
    email: ParsedEmail,
    index: int,
    output_dir: Path,
    skip_conversion: bool = False,
    skip_attachments: bool = False,
) -> dict:
    """Write a single email as markdown and save its attachments.

    Returns metadata dict for the manifest.
    """
    emails_dir = output_dir / "emails"
    emails_dir.mkdir(exist_ok=True)

    date_str = email.date.strftime("%Y-%m-%d") if email.date else "unknown-date"
    subject_slug = _slugify(email.subject)[:60]
    prefix = f"{index:04d}_{date_str}_{subject_slug}"

    # Write email markdown
    email_path = emails_dir / f"{prefix}.md"
    attachment_records = []

    # Process attachments
    if email.attachments and not skip_attachments:
        att_dir = emails_dir / f"{prefix}_attachments"
        for att in email.attachments:
            orig, converted = save_and_convert(att, att_dir, skip_conversion)
            record = {
                "filename": att.filename,
                "content_type": att.content_type,
                "size": att.size,
                "original": str(orig.relative_to(output_dir)),
            }
            if converted:
                record["converted"] = str(converted.relative_to(output_dir))
            attachment_records.append(record)

    # Render markdown
    content = _render_email_markdown(email, attachment_records, output_dir, email_path)
    email_path.write_text(content, encoding="utf-8")

    return {
        "index": index,
        "file": str(email_path.relative_to(output_dir)),
        "message_id": email.message_id,
        "gmail_id": email.gmail_id,
        "from": email.from_addr,
        "to": email.to_addrs,
        "cc": email.cc_addrs,
        "date": email.date.isoformat() if email.date else None,
        "subject": email.subject,
        "labels": email.labels,
        "attachments": attachment_records,
        "word_count": len(email.body_markdown.split()),
    }


def _render_email_markdown(
    email: ParsedEmail,
    attachments: list[dict],
    output_dir: Path,
    email_path: Path,
) -> str:
    """Render an email as a markdown document with YAML frontmatter."""
    lines = ["---"]
    lines.append(f"message_id: {email.message_id}")
    lines.append(f"from: {email.from_addr}")
    lines.append(f"to: {', '.join(email.to_addrs)}")
    if email.cc_addrs:
        lines.append(f"cc: {', '.join(email.cc_addrs)}")
    if email.date:
        lines.append(f"date: {email.date.isoformat()}")
    lines.append(f"subject: \"{_escape_yaml(email.subject)}\"")
    if email.labels:
        lines.append(f"labels: [{', '.join(email.labels)}]")
    if attachments:
        att_names = [a["filename"] for a in attachments]
        lines.append(f"attachments: [{', '.join(att_names)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {email.subject}")
    lines.append("")
    lines.append(email.body_markdown)

    if attachments:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Attachments")
        lines.append("")
        for att in attachments:
            rel_orig = Path(att["original"])
            lines.append(f"- **{att['filename']}** ({att['content_type']}, {_human_size(att['size'])})")
            if "converted" in att:
                rel_conv = Path(att["converted"])
                lines.append(f"  - [Text version]({rel_conv})")

    return "\n".join(lines) + "\n"


def write_manifest(
    email_records: list[dict],
    query: str,
    output_dir: Path,
) -> None:
    """Write manifest.json and manifest.md summarizing the extraction."""
    manifest = {
        "extraction_date": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "total_emails": len(email_records),
        "total_attachments": sum(len(e["attachments"]) for e in email_records),
        "emails": email_records,
    }

    # JSON manifest
    json_path = output_dir / "manifest.json"
    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown manifest
    md_lines = [
        f"# maildigger: `{query}`",
        f"",
        f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"**{len(email_records)}** emails | "
        f"**{manifest['total_attachments']}** attachments",
        "",
        "| # | Date | From | Subject | Attachments |",
        "|---|------|------|---------|-------------|",
    ]

    for rec in email_records:
        date = rec["date"][:10] if rec["date"] else "—"
        from_addr = rec["from"][:40]
        subject = rec["subject"][:50]
        att_count = len(rec["attachments"])
        att_str = f"{att_count} file{'s' if att_count != 1 else ''}" if att_count else "—"
        md_lines.append(f"| {rec['index']} | {date} | {from_addr} | {subject} | {att_str} |")

    md_path = output_dir / "manifest.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-") or "extraction"


def _escape_yaml(text: str) -> str:
    """Escape special characters for YAML string."""
    return text.replace('"', '\\"')


def _human_size(size: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
