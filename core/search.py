from __future__ import annotations
import os
import re
import logging
from typing import Optional, List, Dict

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

LINKEDIN_PROFILE_REGEX = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?',
    re.IGNORECASE
)


class ExternalSearchEngine:
    """
    Search engine integration to discover external LinkedIn profiles
    and founder details when not found directly on the scraped domain.
    """

    def __init__(self):
        self.ddgs = DDGS()

    def _execute_query(self, query: str, max_results: int = 5) -> List[Dict]:
        """Runs a search query with resilient retries to handle transient network/TLS resets."""
        import time
        for attempt in range(3):
            try:
                engine = DDGS()
                results = list(engine.text(query, max_results=max_results))
                if results:
                    return results
            except Exception as e:
                time.sleep(0.4)
        return []

    def search_linkedin_profile(self, name: str, company: str) -> Optional[str]:
        """
        Searches for a specific executive's LinkedIn profile URL.
        Query example: Paul Copplestone Supabase LinkedIn
        """
        if not name or not company:
            return None

        # Clean name from prefixes
        clean_name = re.sub(r'^(dr\.|mr\.|ms\.|mrs\.)\s+', '', name, flags=re.IGNORECASE).strip()
        queries = [
            f"{clean_name} {company} LinkedIn",
            f"{clean_name} LinkedIn"
        ]

        for query in queries:
            results = self._execute_query(query, max_results=4)
            for res in results:
                href = res.get("href", "")
                match = LINKEDIN_PROFILE_REGEX.search(href)
                if match:
                    found_url = match.group(0).rstrip("/")
                    logger.info(f"Discovered LinkedIn URL for {clean_name} ({company}): {found_url}")
                    return found_url

                body = res.get("body", "")
                match = LINKEDIN_PROFILE_REGEX.search(body)
                if match:
                    return match.group(0).rstrip("/")

        return None

    def search_company_founders(self, company: str, domain: str) -> List[Dict[str, str]]:
        """
        Searches for company founders or CEO if leadership wasn't discovered on-site.
        """
        domain_root = domain.lower().replace("www.", "").split(".")[0]
        queries = [
            f"{company} founder CEO LinkedIn",
            f"{company} AI founder LinkedIn",
            f"{domain_root} founders LinkedIn"
        ]
        candidates = []
        seen_urls = set()

        for query in queries:
            results = self._execute_query(query, max_results=4)
            for res in results:
                href = res.get("href", "")
                title = res.get("title", "")
                match = LINKEDIN_PROFILE_REGEX.search(href)
                if match:
                    url = match.group(0).rstrip("/")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        raw_name = title.split("-")[0].split("|")[0].split("–")[0].strip()
                        clean_name = re.sub(rf'^{re.escape(company)}\s*[-:|–]\s*', '', raw_name, flags=re.IGNORECASE).strip()
                        if clean_name and len(clean_name.split()) <= 4 and clean_name.lower() != company.lower():
                            candidates.append({
                                "name": clean_name,
                                "role": "Founder / Executive",
                                "linkedin_url": url
                            })
            if len(candidates) >= 2:
                break

        return candidates

    def search_company_contacts(self, company: str, domain: str) -> Dict[str, List[str]]:
        """
        Searches for company contact emails, phone numbers, and official contact/support URLs.
        """
        emails: Set[str] = set()
        phones: Set[str] = set()
        contact_urls: Set[str] = set()

        email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
        phone_regex = re.compile(r'(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')

        domain_clean = domain.lower().replace("www.", "").strip()
        domain_root = domain_clean.split(".")[0]

        queries = [
            f'"{domain_clean}" contact email',
            f'"{company}" contact email OR support email',
            f'"{domain_clean}" customer service phone OR sales'
        ]

        for query in queries:
            results = self._execute_query(query, max_results=4)
            for res in results:
                text_blob = f"{res.get('title', '')} {res.get('body', '')} {res.get('href', '')}"
                for em in email_regex.findall(text_blob):
                    clean_em = em.lower().strip("<>\"'.,;:")
                    if not any(dummy in clean_em for dummy in ['example.com', 'domain.com', 'email.com', 'sentry.io', 'w3.org', '.png', '.jpg', '.webp']):
                        emails.add(clean_em)

                    for ph in phone_regex.findall(text_blob):
                        clean_ph = ph.strip(" -.,;:")
                        digits_only = re.sub(r'\D', '', clean_ph)
                        if 10 <= len(digits_only) <= 12:
                            phones.add(clean_ph)

                    href = res.get('href', '')
                    if any(k in href.lower() for k in ['contact', 'support', 'sales']) and domain_root in href.lower():
                        contact_urls.add(href)

        # Prioritize emails matching company domain
        domain_emails = [e for e in emails if domain_root in e]
        other_emails = [e for e in emails if e not in domain_emails]
        sorted_emails = domain_emails + other_emails

        return {
            "emails": sorted_emails[:5],
            "phones": list(phones)[:3],
            "contact_urls": list(contact_urls)[:2]
        }
