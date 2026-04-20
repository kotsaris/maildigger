"""Beautiful CLI interface for maildigger."""

import sys

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__

console = Console()


BANNER = """
 [bold cyan]╔══════════════════════════════════════════════╗[/bold cyan]
 [bold cyan]║[/bold cyan]        [bold white]maildigger[/bold white]  [dim]v{version}[/dim]                 [bold cyan]║[/bold cyan]
 [bold cyan]║[/bold cyan]  [dim]Digging up your emails for LLMs[/dim]              [bold cyan]║[/bold cyan]
 [bold cyan]╚══════════════════════════════════════════════╝[/bold cyan]
"""


@click.group()
@click.version_option(__version__, prog_name="maildigger")
def main():
    """Dig Gmail emails and attachments into LLM-friendly markdown."""
    pass


@main.command()
def auth():
    """Authenticate with Gmail using an App Password."""
    console.print(BANNER.format(version=__version__))

    from .auth import check_auth_status, save_config, connect

    status = check_auth_status()
    if status["authenticated"]:
        console.print(f"[green]✓[/green] Already authenticated as [bold]{status['email']}[/bold]")
        if not click.confirm("Re-authenticate with different credentials?", default=False):
            return

    console.print(Panel(
        "[bold]To create an App Password:[/bold]\n"
        "\n"
        "  [cyan]1.[/cyan] Go to [link=https://myaccount.google.com/security]myaccount.google.com/security[/link]\n"
        "  [cyan]2.[/cyan] Ensure [bold]2-Step Verification[/bold] is turned ON\n"
        "  [cyan]3.[/cyan] Go to [link=https://myaccount.google.com/apppasswords]myaccount.google.com/apppasswords[/link]\n"
        "  [cyan]4.[/cyan] Create an app password (name it anything, e.g. 'maildigger')\n"
        "  [cyan]5.[/cyan] Copy the 16-character password shown\n",
        title="[bold yellow]Gmail App Password Setup[/bold yellow]",
        border_style="yellow",
    ))

    email_addr = Prompt.ask("\n  [bold]Gmail address[/bold]")
    app_password = Prompt.ask("  [bold]App password[/bold] [dim](16 chars, spaces ok)[/dim]")

    # Strip spaces from app password (Google shows it with spaces)
    app_password = app_password.replace(" ", "")

    with console.status("[bold cyan]  Verifying credentials..."):
        try:
            imap = connect(email_addr, app_password)
            imap.logout()
        except Exception as e:
            console.print(f"\n  [red]✗ Login failed:[/red] {e}")
            console.print("  [dim]Check your email and app password and try again.[/dim]")
            sys.exit(1)

    save_config(email_addr, app_password)
    console.print(f"\n  [green]✓[/green] Authenticated as [bold]{email_addr}[/bold]")
    console.print("  [dim]Credentials saved to ~/.config/maildigger/config.json (mode 600)[/dim]")


@main.command()
@click.option("--query", "-q", help="Raw Gmail search query (same syntax as Gmail search bar).")
@click.option("--person", "-p", multiple=True, help="Email address to match (both from and to). Repeatable.")
@click.option("--sender", "-s", multiple=True, help="Filter by sender. Repeatable.")
@click.option("--recipient", "-r", multiple=True, help="Filter by recipient. Repeatable.")
@click.option("--after", "-a", help="Start date (YYYY-MM-DD).")
@click.option("--before", "-b", help="End date (YYYY-MM-DD).")
@click.option("--subject", help="Subject line contains.")
@click.option("--has-attachment", is_flag=True, help="Only emails with attachments.")
@click.option("--label", "-l", multiple=True, help="Gmail label filter. Repeatable.")
@click.option("--output", "-o", default="./artifacts", help="Output directory. [default: ./artifacts]")
@click.option("--limit", type=int, help="Maximum number of emails to fetch.")
@click.option("--skip-attachments", is_flag=True, help="Don't download attachments.")
@click.option("--skip-conversion", is_flag=True, help="Download attachments but don't convert to text.")
@click.option("--dry-run", is_flag=True, help="Show query and estimated count without fetching.")
def search(query, person, sender, recipient, after, before, subject,
           has_attachment, label, output, limit, skip_attachments,
           skip_conversion, dry_run):
    """Search and extract emails."""
    console.print(BANNER.format(version=__version__))

    from .auth import connect
    from .search import build_query
    from .fetch import fetch_message_uids, fetch_messages, count_messages
    from .parse import parse_raw_email
    from .output import create_output_dir, write_email, write_manifest

    # Build query
    try:
        gmail_query = build_query(
            raw_query=query,
            persons=list(person) if person else None,
            senders=list(sender) if sender else None,
            recipients=list(recipient) if recipient else None,
            after=after,
            before=before,
            subject=subject,
            has_attachment=has_attachment,
            labels=list(label) if label else None,
        )
    except ValueError as e:
        console.print(f"  [red]✗ Error:[/red] {e}")
        sys.exit(1)

    # Display query
    console.print(Panel(
        f"[bold cyan]{gmail_query}[/bold cyan]",
        title="[bold]Gmail Query[/bold]",
        border_style="blue",
    ))

    # Connect
    with console.status("[bold cyan]  Connecting to Gmail..."):
        try:
            imap = connect()
        except ValueError as e:
            console.print(f"  [red]✗[/red] {e}")
            console.print("  [dim]Run [cyan]maildigger auth[/cyan] first.[/dim]")
            sys.exit(1)
        except Exception as e:
            console.print(f"  [red]✗ Connection error:[/red] {e}")
            sys.exit(1)

    try:
        # Dry run
        if dry_run:
            with console.status("[bold cyan]  Counting results..."):
                total = count_messages(imap, gmail_query)
            console.print(f"\n  [bold]Matching emails:[/bold] {total}")
            if limit:
                console.print(f"  [dim]Would fetch up to {limit}[/dim]")
            return

        # Fetch message UIDs
        console.print()
        with console.status("[bold cyan]  Searching..."):
            uids = fetch_message_uids(imap, gmail_query, limit)

        if not uids:
            console.print("  [yellow]No emails found matching your query.[/yellow]")
            return

        console.print(f"  [green]✓[/green] Found [bold]{len(uids)}[/bold] emails\n")

        # Fetch full messages
        raw_emails = fetch_messages(imap, uids)

        # Sort oldest-first for output numbering
        raw_emails.reverse()

        # Create output directory
        output_dir = create_output_dir(output, gmail_query)
        console.print(f"\n  [green]✓[/green] Output: [bold]{output_dir}[/bold]\n")

        # Parse and write emails
        email_records = []

        from rich.progress import (
            Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing emails...", total=len(raw_emails))

            for i, raw in enumerate(raw_emails, 1):
                parsed = parse_raw_email(raw.raw_mime, raw.uid, raw.gmail_labels)
                record = write_email(
                    parsed, i, output_dir,
                    skip_conversion=skip_conversion,
                    skip_attachments=skip_attachments,
                )
                email_records.append(record)
                progress.update(task, advance=1)

        # Write manifest
        write_manifest(email_records, gmail_query, output_dir)

        # Summary
        total_attachments = sum(len(r["attachments"]) for r in email_records)
        converted = sum(
            1 for r in email_records
            for a in r["attachments"]
            if "converted" in a
        )

        console.print()
        _print_summary(email_records, output_dir, total_attachments, converted)

    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _print_summary(records, output_dir, total_attachments, converted):
    """Print a beautiful extraction summary."""
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column(style="bold")
    stats.add_column()
    stats.add_row("Emails extracted", f"[bold green]{len(records)}[/bold green]")
    stats.add_row("Attachments saved", f"[bold]{total_attachments}[/bold]")
    if converted:
        stats.add_row("Converted to text", f"[bold]{converted}[/bold]")
    stats.add_row("Output directory", f"[cyan]{output_dir}[/cyan]")
    stats.add_row("Manifest", f"[cyan]{output_dir / 'manifest.json'}[/cyan]")

    console.print(Panel(
        stats,
        title="[bold green]✓ Extraction Complete[/bold green]",
        border_style="green",
    ))

    # Preview table
    if records:
        table = Table(
            title="[bold]Email Preview[/bold]",
            box=box.ROUNDED,
            show_lines=False,
            header_style="bold cyan",
            row_styles=["", "dim"],
        )
        table.add_column("#", style="dim", width=5)
        table.add_column("Date", width=12)
        table.add_column("From", width=30, no_wrap=True)
        table.add_column("Subject", width=40)
        table.add_column("Att.", width=5, justify="right")

        display = records[:15]
        for rec in display:
            date = rec["date"][:10] if rec["date"] else "—"
            from_addr = rec["from"][:30]
            subj = rec["subject"][:40]
            att = str(len(rec["attachments"])) if rec["attachments"] else "—"
            table.add_row(str(rec["index"]), date, from_addr, subj, att)

        if len(records) > 15:
            table.add_row(
                "...", "", f"[dim]and {len(records) - 15} more[/dim]", "", ""
            )

        console.print(table)


@main.command()
def status():
    """Check authentication status."""
    from .auth import check_auth_status, CONFIG_PATH

    console.print(BANNER.format(version=__version__))

    result = check_auth_status()

    if result["authenticated"]:
        console.print(f"  [green]✓[/green] Authenticated as [bold]{result['email']}[/bold]")
        console.print(f"  [dim]Config: {CONFIG_PATH}[/dim]")
    else:
        console.print(f"  [red]✗[/red] Not authenticated: {result['reason']}")
        console.print(f"  [dim]Run [cyan]maildigger auth[/cyan] to set up credentials.[/dim]")


if __name__ == "__main__":
    main()
