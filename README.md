<p align="center">
  <img src="docs/logo.png" alt="maildigger — digging up your emails" width="600" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Gmail-IMAP-EA4335?style=for-the-badge&logo=gmail&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM-Ready-blueviolet?style=for-the-badge" />
</p>

# `maildigger`

> **Dig your Gmail into structured, LLM-ready markdown in one command.**

Extract emails and attachments from Gmail into clean markdown files with YAML frontmatter. PDFs, DOCX, XLSX, PPTX are auto-converted to text. Zero Google Cloud setup — just an App Password and you're in.

```bash
maildigger search -q "from:accountant@example.com after:2025/01/01 has:attachment"
```

```
 ╔══════════════════════════════════════════════╗
 ║        maildigger  v0.1.0                   ║
 ║  Digging up your emails for LLMs            ║
 ╚══════════════════════════════════════════════╝

 ✓ Found 57 emails

 Processing emails... ━━━━━━━━━━━━━━━━━━━━ 57/57

 ┌──────────── ✓ Extraction Complete ────────────┐
 │ Emails extracted    57                         │
 │ Attachments saved   176                        │
 │ Converted to text   23                         │
 └────────────────────────────────────────────────┘
```

---

## Why?

You've got years of invoices, contracts, statements, and correspondence buried in Gmail. You want to feed them to an LLM — but Gmail gives you `.eml` blobs and nested MIME trees.

**`maildigger`** turns that mess into a clean folder of markdown files and converted attachments that any LLM can consume directly.

**No Google Cloud project. No OAuth dance. No API keys.** Just a 16-character App Password over IMAP.

---

## Quickstart

### 1. Install

```bash
pip install -e .
```

### 2. Authenticate

```bash
maildigger auth
```

You'll need a [Gmail App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification). That's the only setup.

### 3. Extract

```bash
# Use Gmail's exact search syntax
maildigger search -q "from:alice@example.com after:2025/01/01"

# Or structured filters
maildigger search --sender boss@company.com --has-attachment --after 2025-06-01

# Dry run — see what matches without downloading
maildigger search -q "label:important" --dry-run
```

---

## Search Examples

```bash
# Everything from a sender with attachments
maildigger search -q "from:invoices@vendor.com has:attachment"

# Subject search within a date range
maildigger search -q "subject:invoice after:2024/06/01 before:2024/12/31"

# Multiple people (finds emails involving any of them)
maildigger search -p alice@example.com -p bob@example.com --after 2025-01-01

# Label + starred
maildigger search -q "label:finance is:starred"

# Full-text body search
maildigger search -q "quarterly report budget"

# Cap results
maildigger search -q "from:reports@company.com" --limit 50

# Custom output directory
maildigger search -q "label:projects" -o ./my-exports
```

---

## Output

Each run creates a timestamped, self-contained folder:

```
artifacts/
└── 2026-03-28_143052_from-alice-example-com/
    ├── manifest.json                              # Machine-readable index
    ├── manifest.md                                # Human-readable summary
    └── emails/
        ├── 0001_2025-06-15_q3-planning.md         # Email as markdown
        ├── 0001_..._attachments/
        │   ├── report.pdf                         # Original
        │   ├── report.pdf.txt                     # Extracted text
        │   ├── budget.xlsx                        # Original
        │   └── budget.xlsx.csv                    # Converted to CSV
        ├── 0002_2025-06-16_re-q3-planning.md
        └── ...
```

### Email Format

Every email becomes a self-contained markdown file:

```markdown
---
message_id: <abc123@mail.gmail.com>
from: Alice Smith <alice@example.com>
to: Bob Jones <bob@example.com>
date: 2025-06-15T10:30:00-07:00
subject: "Q3 Planning Document"
attachments: [report.pdf, budget.xlsx]
---

# Q3 Planning Document

Hi Bob,

Here's the Q3 planning document we discussed...
```

### Metadata File (`manifest.json`)

Each extraction includes a machine-readable manifest with full metadata:

```json
{
  "extraction_date": "2026-03-28T20:43:06.241721+00:00",
  "query": "from:invoices@vendor.com has:attachment",
  "total_emails": 57,
  "total_attachments": 176,
  "emails": [
    {
      "index": 1,
      "file": "emails/0001_2025-06-15_q3-planning.md",
      "message_id": "<abc123@mail.gmail.com>",
      "gmail_id": "98401",
      "from": "Alice Smith <alice@example.com>",
      "to": ["Bob Jones <bob@example.com>"],
      "cc": [],
      "date": "2025-06-15T10:30:00-07:00",
      "subject": "Q3 Planning Document",
      "labels": ["\\Important"],
      "attachments": [
        {
          "filename": "report.pdf",
          "content_type": "application/pdf",
          "size": 245120,
          "original": "emails/0001_..._attachments/report.pdf",
          "converted": "emails/0001_..._attachments/report.pdf.txt"
        },
        {
          "filename": "budget.xlsx",
          "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "size": 18432,
          "original": "emails/0001_..._attachments/budget.xlsx",
          "converted": "emails/0001_..._attachments/budget.xlsx.csv"
        }
      ],
      "word_count": 342
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `extraction_date` | string | ISO 8601 timestamp (UTC) of when the extraction ran |
| `query` | string | Gmail search query used |
| `total_emails` | int | Number of emails extracted |
| `total_attachments` | int | Total attachments across all emails |
| `emails[].index` | int | Sequential 1-based index |
| `emails[].file` | string | Relative path to the email markdown file |
| `emails[].message_id` | string | RFC 822 Message-ID header |
| `emails[].gmail_id` | string | Gmail internal UID |
| `emails[].from` | string | Sender (display name + address) |
| `emails[].to` | string[] | Recipient addresses |
| `emails[].cc` | string[] | CC addresses (empty array if none) |
| `emails[].date` | string\|null | ISO 8601 datetime, or `null` if unparseable |
| `emails[].subject` | string | Email subject line |
| `emails[].labels` | string[] | Gmail labels |
| `emails[].attachments` | object[] | Attachment records (see below) |
| `emails[].word_count` | int | Word count of the email body |
| `attachments[].filename` | string | Original filename |
| `attachments[].content_type` | string | MIME type |
| `attachments[].size` | int | Size in bytes |
| `attachments[].original` | string | Relative path to the saved file |
| `attachments[].converted` | string? | Relative path to converted text (only present if conversion succeeded) |

### Auto-Conversion

| Format | Converts To | How |
|--------|------------|-----|
| PDF | `.pdf.txt` | pdfplumber (page-by-page) |
| DOCX | `.docx.txt` | python-docx |
| XLSX | `.xlsx.csv` | openpyxl (per-sheet) |
| PPTX | `.pptx.txt` | python-pptx (per-slide) |
| HTML | `.html.md` | beautifulsoup4 + markdownify |
| Images | kept as-is | multimodal LLMs handle these directly |

Conversion is best-effort — if it fails, the original is always preserved.

---

## Feeding to LLMs

This tool was built specifically for LLM workflows:

1. **Start with the manifest** — `manifest.md` gives the LLM a bird's-eye view of all emails
2. **Drill into individual emails** — each `.md` file is self-contained with full metadata
3. **Converted attachments are ready to paste** — `.txt` and `.csv` files go straight into context
4. **Images work with multimodal models** — Claude, GPT-4o, Gemini can read them directly

### Example: Claude Code workflow

```bash
# Extract all emails from a vendor
maildigger search -q "from:invoices@vendor.com"

# Then in Claude Code, just point at the output
# "Study the emails in artifacts/ and build me a 2025 expense report"
```

---

## Dependencies

All lightweight, well-maintained libraries. **No Google API client libraries** — just Python's built-in `imaplib` talking to Gmail's IMAP server.

| Library | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich` | Beautiful terminal output |
| `pdfplumber` | PDF text extraction |
| `python-docx` | DOCX text extraction |
| `openpyxl` | XLSX to CSV conversion |
| `python-pptx` | PPTX text extraction |
| `beautifulsoup4` + `markdownify` | HTML to Markdown |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No saved credentials" | Run `maildigger auth` |
| "Login failed" | Use an **App Password** (16 chars), not your regular password |
| "Application-specific password required" | Generate one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |
| Empty results | Check the query works in Gmail's search bar first. Emails in Trash won't match. |
| Slow extraction | IMAP is sequential. Use `--limit` for large mailboxes. |
| IMAP disabled | Gmail Settings > Forwarding and POP/IMAP > Enable IMAP |

---

## License

MIT

---

<p align="center">
  <sub>Built for the age of LLMs. Stop copy-pasting from Gmail.</sub>
</p>
