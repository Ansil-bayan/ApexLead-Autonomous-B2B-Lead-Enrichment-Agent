from __future__ import annotations
import asyncio
import re
import logging
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Keywords identifying target subpages
SUBPAGE_KEYWORDS = [
    'about', 'team', 'company', 'leadership', 'contact', 
    'pricing', 'people', 'founders', 'management', 'who-we-are'
]

# Standard realistic desktop headers
STANDARD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


class CrawlResult:
    def __init__(self, url: str, html: str, status_code: int = 200, error: Optional[str] = None):
        self.url = url
        self.html = html
        self.status_code = status_code
        self.error = error

    @property
    def is_success(self) -> bool:
        return bool(self.html and len(self.html.strip()) > 100 and not self.error)


class PlaywrightCrawler:
    """
    Headless Playwright-based crawler with dynamic JS execution,
    automatic subpage discovery, and resilient HTTPX fallback.
    """

    def __init__(
        self,
        headless: bool = True,
        page_timeout_ms: int = 15000,
        max_subpages: int = 5
    ):
        self.headless = headless
        self.page_timeout_ms = page_timeout_ms
        self.max_subpages = max_subpages

    def normalize_domain_url(self, domain: str) -> str:
        domain = domain.strip().lower()
        if not domain.startswith("http://") and not domain.startswith("https://"):
            domain = f"https://{domain}"
        return domain

    async def crawl_domain(self, domain_input: str) -> Dict[str, CrawlResult]:
        """
        Main entry point for crawling a single domain.
        Fetches homepage, discovers relevant subpages, and crawls them.
        Returns a dict of {url: CrawlResult}. Never raises exceptions.
        """
        results: Dict[str, CrawlResult] = {}
        base_url = self.normalize_domain_url(domain_input)
        parsed_base = urlparse(base_url)
        base_netloc = parsed_base.netloc.replace("www.", "")

        logger.info(f"Starting crawl for {base_url}")

        playwright_obj = None
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None

        try:
            playwright_obj = await async_playwright().start()
            browser = await playwright_obj.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ]
            )
            context = await browser.new_context(
                user_agent=STANDARD_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                ignore_https_errors=True
            )

            # 1. Fetch homepage
            home_result = await self._fetch_page_playwright(context, base_url)
            if not home_result.is_success:
                logger.warning(f"Playwright failed for {base_url}, attempting HTTPX fallback...")
                home_result = await self._fetch_page_httpx(base_url)

            results[base_url] = home_result

            # If homepage fetched successfully, discover and fetch subpages
            if home_result.is_success:
                discovered_urls = self.discover_subpages(home_result.html, base_url, base_netloc)
                logger.info(f"Discovered {len(discovered_urls)} subpages for {base_url}: {discovered_urls}")

                # Crawl discovered subpages (up to max_subpages)
                for sub_url in discovered_urls[:self.max_subpages]:
                    if sub_url in results:
                        continue
                    sub_res = await self._fetch_page_playwright(context, sub_url)
                    if not sub_res.is_success:
                        sub_res = await self._fetch_page_httpx(sub_url)
                    results[sub_url] = sub_res

        except Exception as e:
            logger.error(f"Error during Playwright crawl of {base_url}: {e}")
            # Resilient fallback to HTTPX for homepage if not already fetched
            if base_url not in results or not results[base_url].is_success:
                fallback_res = await self._fetch_page_httpx(base_url)
                results[base_url] = fallback_res
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright_obj:
                try:
                    await playwright_obj.stop()
                except Exception:
                    pass

        return results

    async def _fetch_page_playwright(self, context: BrowserContext, url: str) -> CrawlResult:
        page: Optional[Page] = None
        try:
            page = await context.new_page()
            # Set route abort for heavy media to speed up crawling
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
            )
            response = await page.goto(
                url, 
                wait_until="domcontentloaded", 
                timeout=self.page_timeout_ms
            )
            # Brief wait for client-side rendering
            await asyncio.sleep(1.0)
            
            content = await page.content()
            status = response.status if response else 200
            return CrawlResult(url=url, html=content, status_code=status)
        except PlaywrightTimeoutError:
            # If timeout occurred, page content might still have loaded partially
            if page:
                try:
                    partial_content = await page.content()
                    if len(partial_content) > 500:
                        return CrawlResult(url=url, html=partial_content, status_code=200)
                except Exception:
                    pass
            return CrawlResult(url=url, html="", error="Playwright Timeout")
        except Exception as e:
            return CrawlResult(url=url, html="", error=str(e))
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _fetch_page_httpx(self, url: str) -> CrawlResult:
        """Fallback asynchronous HTTP request using HTTPX."""
        try:
            async with httpx.AsyncClient(
                headers=STANDARD_HEADERS, 
                follow_redirects=True, 
                timeout=12.0, 
                verify=False
            ) as client:
                resp = await client.get(url)
                return CrawlResult(url=str(resp.url), html=resp.text, status_code=resp.status_code)
        except Exception as e:
            return CrawlResult(url=url, html="", error=f"HTTPX error: {str(e)}")

    def discover_subpages(self, html: str, base_url: str, base_netloc: str) -> List[str]:
        """
        Parses anchor tags in the homepage HTML and identifies relevant
        subpages (about, team, pricing, contact, etc.) on the same domain.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        discovered: Set[str] = set()
        scored_candidates: List[tuple[int, str]] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            parsed_netloc = parsed.netloc.replace("www.", "")

            # Ensure same domain
            if parsed_netloc != base_netloc:
                continue

            clean_path = parsed.path.lower().rstrip("/")
            if not clean_path or clean_path in ["", "/"]:
                continue

            # Check for keyword matches in path or anchor text
            anchor_text = a.get_text(strip=True).lower()
            combined_context = f"{clean_path} {anchor_text}"

            score = 0
            for kw in SUBPAGE_KEYWORDS:
                if kw in clean_path:
                    score += 3
                elif kw in anchor_text:
                    score += 2

            # Prioritize team, about, leadership, founders
            if any(k in clean_path for k in ['team', 'leadership', 'about', 'company', 'founders', 'people']):
                score += 8
            elif any(k in clean_path for k in ['contact', 'contact-us', 'support', 'sales']):
                score += 6

            if score > 0:
                canonical_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if canonical_url not in discovered:
                    discovered.add(canonical_url)
                    scored_candidates.append((score, canonical_url))

        # Ensure contact endpoints are considered if not discovered in anchor tags
        has_contact = any('contact' in url or 'support' in url for url in discovered)
        if not has_contact:
            for probe_path in ['/contact', '/contact-us']:
                probe_url = f"{base_url.rstrip('/')}{probe_path}"
                if probe_url not in discovered:
                    discovered.add(probe_url)
                    scored_candidates.append((5, probe_url))

        # Partition into about/team, contact, and general candidates for balanced selection
        about_candidates = []
        contact_candidates = []
        other_candidates = []

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        for _, url in scored_candidates:
            url_lower = url.lower()
            if any(k in url_lower for k in ['team', 'leadership', 'about', 'company', 'founders', 'people', 'who-we-are']):
                about_candidates.append(url)
            elif any(k in url_lower for k in ['contact', 'support', 'sales']):
                contact_candidates.append(url)
            else:
                other_candidates.append(url)

        # Balanced selection: Top 2-3 about/leadership pages + Top 2 contact pages
        balanced: List[str] = []
        balanced.extend(about_candidates[:3])
        balanced.extend(contact_candidates[:2])
        for u in other_candidates:
            if len(balanced) < 5 and u not in balanced:
                balanced.append(u)

        return balanced
