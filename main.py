from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from core.agent import LeadEnrichmentAgent
from core.models import EnrichedLead

console = Console()

DEFAULT_DOMAINS = [
    "postman.com",
    "supabase.com",
    "vapi.ai"
]


def render_lead_panel(lead: EnrichedLead):
    """Renders a visually polished Rich panel for a single enriched lead."""
    table = Table(show_header=False, box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("Field", style="bold green", width=24)
    table.add_column("Value", style="white")

    table.add_row("Company Name", lead.company_name)
    table.add_row("Domain", lead.domain)
    table.add_row("Company Overview", lead.company_overview)
    table.add_row("Target Audience / ICP", lead.target_audience_icp)
    table.add_row("Contact Points", ", ".join(lead.contact_points) if lead.contact_points else "None found")

    # Leadership
    if lead.key_leadership:
        lead_str = "\n".join([
            f"• {m.name} ({m.role}) [link={m.linkedin_url or ''}]{m.linkedin_url or 'No LinkedIn'}[/link]"
            for m in lead.key_leadership
        ])
    else:
        lead_str = "None discovered"
    table.add_row("Key Leadership", lead_str)

    confidence_color = "green" if lead.data_confidence_score >= 0.8 else "yellow" if lead.data_confidence_score >= 0.5 else "red"
    table.add_row("Confidence Score", f"[{confidence_color}]{lead.data_confidence_score * 100:.0f}%[/{confidence_color}]")
    table.add_row("Sources Crawled", f"{len(lead.sources_crawled)} pages: " + ", ".join(lead.sources_crawled[:3]))
    table.add_row("Token & Cost", f"{lead.cost_metrics.total_tokens:,} tokens (${lead.cost_metrics.estimated_cost_usd:.5f})")
    table.add_row("Search Fallback Used", "Yes" if lead.external_search_used else "No")

    console.print(Panel(table, title=f"[bold white on blue] {lead.company_name} ({lead.domain}) [/]", border_style="bright_blue"))


def render_summary_table(leads: List[EnrichedLead]):
    """Renders an executive summary table across all processed domains."""
    table = Table(title="[bold cyan]Lead Enrichment Summary[/bold cyan]", box=box.ROUNDED)
    table.add_column("Domain", style="cyan bold")
    table.add_column("Company", style="white")
    table.add_column("ICP (Target Audience)", style="magenta")
    table.add_column("Contacts", style="green")
    table.add_column("Leadership Count", justify="center")
    table.add_column("Confidence", justify="center")
    table.add_column("Cost (USD)", justify="right")

    total_cost = 0.0
    total_tokens = 0

    for lead in leads:
        conf_style = "bold green" if lead.data_confidence_score >= 0.8 else "bold yellow"
        table.add_row(
            lead.domain,
            lead.company_name,
            lead.target_audience_icp[:45] + ("..." if len(lead.target_audience_icp) > 45 else ""),
            str(len(lead.contact_points)),
            str(len(lead.key_leadership)),
            f"[{conf_style}]{lead.data_confidence_score:.2f}[/{conf_style}]",
            f"${lead.cost_metrics.estimated_cost_usd:.5f}"
        )
        total_cost += lead.cost_metrics.estimated_cost_usd
        total_tokens += lead.cost_metrics.total_tokens

    console.print(table)
    console.print(f"[bold green]Total Tokens Consumed:[/] {total_tokens:,} | [bold green]Total Estimated Cost:[/] ${total_cost:.5f}\n")


async def async_main(domains: List[str], output_path: str, headless: bool):
    console.print(Panel.fit(
        "[bold cyan]Autonomous Lead Enrichment Agent[/bold cyan]\n"
        "[dim]Playwright Headless Crawling • Token Optimization • Structured LLM Extraction • External Search[/dim]",
        border_style="cyan"
    ))
    console.print(f"[bold yellow]Target Domains ({len(domains)}):[/] {', '.join(domains)}\n")

    has_api_key = any(os.getenv(k, "").strip() for k in ["GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"])
    if not has_api_key:
        console.print("[bold red][ERROR] Please provide an API key.[/bold red] Set GEMINI_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY in your .env file to run LLM extraction.\n")
        return

    agent = LeadEnrichmentAgent(headless=headless)

    def cli_progress(step: str, msg: str):
        color = {
            "BROWSE": "cyan",
            "OPTIMIZE": "blue",
            "EXTRACT": "magenta",
            "SEARCH": "yellow",
            "COMPLETE": "green",
            "ERROR": "red"
        }.get(step, "white")
        console.print(f"[{color}][{step}][/{color}] {msg}")

    leads = await agent.enrich_multiple_domains(domains, progress_callback=cli_progress)

    console.print("\n[bold green]Enrichment Pipeline Completed![/bold green]\n")

    for lead in leads:
        render_lead_panel(lead)

    render_summary_table(leads)

    # Save output JSON
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json_data = [lead.model_dump() for lead in leads]
        json.dump(json_data, f, indent=2)

    console.print(f"[bold green][OK] Structured intelligence exported to:[/] [underline]{out_file.resolve()}[/underline]\n")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Lead Enrichment Agent")
    parser.add_argument(
        "--domains", 
        nargs="+", 
        default=DEFAULT_DOMAINS,
        help="List of company domains to enrich (e.g. postman.com supabase.com vapi.ai)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="output/enriched_leads.json",
        help="Path to output JSON file"
    )
    parser.add_argument(
        "--no-headless", 
        action="store_true", 
        help="Run browser in visible mode for debugging"
    )
    args = parser.parse_args()

    asyncio.run(async_main(
        domains=args.domains, 
        output_path=args.output, 
        headless=not args.no_headless
    ))


if __name__ == "__main__":
    main()
