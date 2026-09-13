from __future__ import annotations
import asyncio
import logging
import re
from typing import Callable, List, Optional

from core.models import EnrichedLead, LeadershipMember, TokenUsage
from core.crawler import PlaywrightCrawler
from core.preprocessor import ContentPreprocessor
from core.llm import StructuredExtractor, MissingAPIKeyError
from core.search import ExternalSearchEngine

logger = logging.getLogger(__name__)


class LeadEnrichmentAgent:
    """
    Autonomous multi-step agent orchestrator that coordinates browsing,
    content pre-processing, structured LLM extraction, external search enrichment,
    and token/cost tracking.
    """

    def __init__(
        self,
        headless: bool = True,
        max_subpages: int = 4,
        enable_search_fallback: bool = True,
        llm_provider: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.crawler = PlaywrightCrawler(headless=headless, max_subpages=max_subpages)
        self.preprocessor = ContentPreprocessor()
        self.extractor = StructuredExtractor(provider=llm_provider, api_key=api_key)
        self.search_engine = ExternalSearchEngine()
        self.enable_search_fallback = enable_search_fallback

    async def enrich_domain(
        self, 
        domain: str, 
        progress_callback: Optional[Callable[[str, str], None]] = None
    ) -> EnrichedLead:
        """
        Enriches a single domain through the complete autonomous pipeline.
        progress_callback: fn(step_name, message) for live UI/CLI updates.
        """
        def notify(step: str, msg: str):
            if progress_callback:
                progress_callback(step, msg)
            logger.info(f"[{domain}] [{step}] {msg}")

        domain_clean = domain.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")

        # Pre-flight check: ensure API key exists before starting headless browser or crawling
        active_key = (
            self.extractor.gemini_key if self.extractor.provider == "gemini"
            else self.extractor.openai_key if self.extractor.provider == "openai"
            else self.extractor.groq_key
        )
        if not active_key:
            err_msg = f"No API key provided for {self.extractor.provider.upper()}. Please provide an API key."
            notify("ERROR", err_msg)
            raise MissingAPIKeyError(err_msg)

        notify("BROWSE", f"Initiating headless crawl for {domain_clean}...")

        # 1. Automated Crawling
        try:
            crawl_results = await self.crawler.crawl_domain(domain_clean)
        except Exception as e:
            notify("ERROR", f"Crawl error: {e}")
            crawl_results = {}

        successful_pages = [url for url, res in crawl_results.items() if res.is_success]
        notify("BROWSE", f"Fetched {len(successful_pages)} pages: {', '.join(successful_pages) if successful_pages else 'None'}")

        if not successful_pages:
            notify("FALLBACK", "Direct pages inaccessible, generating initial baseline lead...")
            return EnrichedLead(
                domain=domain_clean,
                company_name=domain_clean.split(".")[0].capitalize(),
                company_overview=f"Web presence for {domain_clean} is currently behind high bot security or unreachable.",
                target_audience_icp="Unknown",
                contact_points=[],
                key_leadership=[],
                data_confidence_score=0.10,
                sources_crawled=[],
                cost_metrics=TokenUsage(),
                error="Could not fetch website content."
            )

        # 2. Context Pre-Processing & Token Optimization
        notify("OPTIMIZE", "Pre-processing HTML trees and stripping noise (CSS, SVGs, scripts)...")
        combined_markdown = []
        all_emails = set()
        all_phones = set()
        all_contact_pages = set()
        all_linkedin_links = set()
        total_raw_chars = 0
        total_clean_chars = 0

        def page_sort_priority(item):
            url_str = item[0].lower()
            if any(k in url_str for k in ['team', 'leadership', 'about', 'company', 'founders', 'people', 'who-we-are']):
                return 1
            if any(k in url_str for k in ['pricing']):
                return 2
            if any(k in url_str for k in ['contact', 'sales', 'support']):
                return 3
            return 0  # Homepage first

        sorted_pages = sorted(crawl_results.items(), key=page_sort_priority)

        for url, res in sorted_pages:
            if not res.is_success:
                continue
            clean_md, meta = self.preprocessor.process_html(res.html, url=url)
            total_raw_chars += meta["original_chars"]
            total_clean_chars += meta["cleaned_chars"]
            for em in meta.get("emails", []):
                all_emails.add(em)
            for ph in meta.get("phones", []):
                all_phones.add(ph)
            for cp in meta.get("contact_pages", []):
                all_contact_pages.add(cp)
            for lk in meta.get("linkedin_urls", []):
                all_linkedin_links.add(lk)

            combined_markdown.append(f"--- SOURCE: {url} ---\n{clean_md}\n")

        merged_content = "\n".join(combined_markdown)
        reduction_pct = round(
            max(0.0, (total_raw_chars - total_clean_chars) / max(1, total_raw_chars)) * 100, 
            1
        )
        notify("OPTIMIZE", f"Optimized tokens: compressed {total_raw_chars:,} chars to {total_clean_chars:,} chars ({reduction_pct}% reduction).")

        # 3. LLM Extraction (Structured Outputs)
        notify("EXTRACT", "Running structured LLM extraction (Pydantic schema validation)...")
        try:
            extracted, cost_usage = self.extractor.extract_intelligence(
                domain=domain_clean,
                content_markdown=merged_content,
                pre_extracted_emails=list(all_emails),
                pre_extracted_linkedin=list(all_linkedin_links),
                pre_extracted_phones=list(all_phones),
                pre_extracted_contact_pages=list(all_contact_pages)
            )
            notify("EXTRACT", f"Extracted overview & {len(extracted.key_leadership)} leadership profiles. Tokens used: {cost_usage.total_tokens:,} (Cost: ${cost_usage.estimated_cost_usd:.5f})")
        except Exception as e:
            notify("ERROR", f"LLM extraction error: {e}")
            return EnrichedLead(
                domain=domain_clean,
                company_name=domain_clean.split(".")[0].capitalize(),
                company_overview=f"Extraction failed: {e}",
                target_audience_icp="N/A",
                contact_points=list(all_emails) + list(all_phones) + list(all_contact_pages),
                key_leadership=[],
                data_confidence_score=0.0,
                sources_crawled=successful_pages,
                cost_metrics=TokenUsage(),
                error=str(e)
            )

        # 4. Search Integration: Enrich missing LinkedIn URLs & Contact Points
        external_search_triggered = False
        if self.enable_search_fallback:
            # Check if any leadership member is missing a LinkedIn profile
            for member in extracted.key_leadership:
                if not member.linkedin_url:
                    notify("SEARCH", f"Searching external LinkedIn profile for {member.name} ({extracted.company_name})...")
                    linkedin_url = self.search_engine.search_linkedin_profile(member.name, extracted.company_name)
                    if linkedin_url:
                        member.linkedin_url = linkedin_url
                        external_search_triggered = True
                        notify("SEARCH", f"Found LinkedIn for {member.name}: {linkedin_url}")

            # If no leadership was found at all, search for founders
            if not extracted.key_leadership:
                notify("SEARCH", f"No leadership found on site. Searching external search for {extracted.company_name} founders...")
                founder_candidates = self.search_engine.search_company_founders(extracted.company_name, domain_clean)
                if founder_candidates:
                    for fc in founder_candidates:
                        extracted.key_leadership.append(
                            LeadershipMember(
                                name=fc["name"],
                                role=fc["role"],
                                linkedin_url=fc["linkedin_url"]
                            )
                        )
                    external_search_triggered = True
                    notify("SEARCH", f"Discovered {len(founder_candidates)} founders via search engine.")

            # Search fallback for contacts if no direct emails discovered
            current_emails = [c for c in extracted.contact_points if "@" in c] or list(all_emails)
            if not current_emails:
                notify("SEARCH", f"No contact email found on site. Searching external web for {extracted.company_name} contacts...")
                search_contacts = self.search_engine.search_company_contacts(extracted.company_name, domain_clean)
                if search_contacts.get("emails") or search_contacts.get("phones") or search_contacts.get("contact_urls"):
                    for em in search_contacts.get("emails", []):
                        all_emails.add(em)
                    for ph in search_contacts.get("phones", []):
                        all_phones.add(ph)
                    for cu in search_contacts.get("contact_urls", []):
                        all_contact_pages.add(cu)
                    external_search_triggered = True
                    notify("SEARCH", f"Discovered contacts via search: {', '.join(search_contacts.get('emails', [])[:2] or search_contacts.get('phones', [])[:1])}")

        # Consolidate all contacts: emails first, phones, then direct contact URLs
        consolidated_contacts = []
        seen_contacts = set()

        for em in list(all_emails) + [c for c in extracted.contact_points if "@" in c]:
            em_clean = em.strip().lower()
            if em_clean and em_clean not in seen_contacts:
                seen_contacts.add(em_clean)
                consolidated_contacts.append(em_clean)

        for ph in list(all_phones) + [c for c in extracted.contact_points if re.search(r'\d{3}[-.\s]?\d{4}', c)]:
            ph_clean = ph.strip()
            if ph_clean and ph_clean not in seen_contacts:
                seen_contacts.add(ph_clean)
                consolidated_contacts.append(ph_clean)

        for cp in list(all_contact_pages) + [c for c in extracted.contact_points if c.startswith("http")]:
            cp_clean = cp.strip()
            if cp_clean and cp_clean not in seen_contacts:
                seen_contacts.add(cp_clean)
                consolidated_contacts.append(cp_clean)

        for c in extracted.contact_points:
            c_clean = c.strip()
            if c_clean and c_clean not in seen_contacts:
                seen_contacts.add(c_clean)
                consolidated_contacts.append(c_clean)

        # 5. Dynamic Confidence Score Adjustment
        score = extracted.data_confidence_score
        # Check completeness
        if not consolidated_contacts:
            score = max(0.1, score - 0.15)
        else:
            if any("@" in c for c in consolidated_contacts):
                score = min(1.0, score + 0.05)

        if not extracted.key_leadership:
            score = max(0.1, score - 0.20)
        else:
            has_linkedin = any(m.linkedin_url for m in extracted.key_leadership)
            if has_linkedin:
                score = min(1.0, score + 0.05)
        final_confidence = round(score, 2)

        notify("COMPLETE", f"Enrichment completed with confidence score: {final_confidence}")

        return EnrichedLead(
            domain=domain_clean,
            company_name=extracted.company_name,
            company_overview=extracted.company_overview,
            target_audience_icp=extracted.target_audience_icp,
            contact_points=consolidated_contacts,
            key_leadership=extracted.key_leadership,
            data_confidence_score=final_confidence,
            sources_crawled=successful_pages,
            cost_metrics=cost_usage,
            external_search_used=external_search_triggered
        )

    async def enrich_multiple_domains(
        self, 
        domains: List[str], 
        progress_callback: Optional[Callable[[str, str], None]] = None
    ) -> List[EnrichedLead]:
        """
        Enriches a batch of domains sequentially with resilient error isolation.
        """
        results: List[EnrichedLead] = []
        for domain in domains:
            try:
                lead = await self.enrich_domain(domain, progress_callback=progress_callback)
                results.append(lead)
            except Exception as e:
                logger.error(f"Unexpected unhandled error on domain {domain}: {e}")
                results.append(
                    EnrichedLead(
                        domain=domain,
                        company_name=domain.split(".")[0].capitalize(),
                        company_overview=f"Failed to enrich domain due to unexpected error: {e}",
                        target_audience_icp="Unknown",
                        contact_points=[],
                        key_leadership=[],
                        data_confidence_score=0.0,
                        sources_crawled=[],
                        cost_metrics=TokenUsage(),
                        error=str(e)
                    )
                )
        return results
