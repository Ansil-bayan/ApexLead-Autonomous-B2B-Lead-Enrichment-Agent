from __future__ import annotations
import re
from typing import Dict, List, Set, Tuple
from bs4 import BeautifulSoup, Comment
import html2text

# Email extraction regex (standard RFC 5322 compliant subset)
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

# LinkedIn URL regex
LINKEDIN_REGEX = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company|school)/[a-zA-Z0-9_-]+/?',
    re.IGNORECASE
)

# Unwanted HTML tags
UNWANTED_TAGS = [
    'script', 'style', 'svg', 'canvas', 'noscript', 'iframe', 'template',
    'video', 'audio', 'picture', 'source', 'track', 'map', 'area', 'embed', 'object'
]

# Elements commonly representing modals, cookie banners, tracking, ads
BOILERPLATE_CLASSES_OR_IDS = [
    'cookie', 'consent', 'gdpr', 'banner-cookie', 'modal-backdrop',
    'ad-banner', 'advertisement', 'newsletter-popup'
]


# Phone number extraction regex (requires phone delimiters like parentheses, dashes, or dots)
PHONE_REGEX = re.compile(r'(?:\+?1[-.\s]?)?(?:\([2-9]\d{2}\)|[2-9]\d{2})[-.\s][2-9]\d{2}[-.\s]\d{4}\b')


class ContentPreprocessor:
    """Pre-processes raw HTML pages into clean, token-optimized semantic Markdown."""

    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_images = True
        self.html_converter.ignore_links = False
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # No wrapping
        self.html_converter.skip_internal_links = True

    def process_html(self, raw_html: str, url: str = "") -> Tuple[str, Dict]:
        """
        Takes raw HTML, strips noise, extracts raw contact hints, and returns
        clean markdown along with extraction metadata.
        """
        if not raw_html or not raw_html.strip():
            return "", {"original_chars": 0, "cleaned_chars": 0, "token_reduction_pct": 0.0, "emails": [], "phones": [], "contact_pages": [], "linkedin_urls": []}

        original_chars = len(raw_html)
        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Extract potential emails, phones, contact links, and linkedin links before stripping tags
        emails = self._extract_emails(soup, raw_html)
        phones = self._extract_phones(soup, raw_html)
        contact_pages = self._extract_contact_links(soup, url)
        linkedin_urls = self._extract_linkedin_urls(soup, raw_html)

        # 2. Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 3. Strip unwanted tags
        for tag_name in UNWANTED_TAGS:
            for el in soup.find_all(tag_name):
                el.decompose()

        # 4. Strip boilerplate containers (cookie banners, popups)
        for selector in BOILERPLATE_CLASSES_OR_IDS:
            for el in soup.find_all(attrs={"class": re.compile(selector, re.I)}):
                el.decompose()
            for el in soup.find_all(attrs={"id": re.compile(selector, re.I)}):
                el.decompose()

        # 5. Clean up base64 attributes and overly long attributes
        for tag in soup.find_all(True):
            attrs_to_remove = []
            for attr, val in tag.attrs.items():
                if isinstance(val, str) and (val.startswith("data:image") or len(val) > 300):
                    attrs_to_remove.append(attr)
            for attr in attrs_to_remove:
                del tag[attr]

        # 6. Prefer main/article content if present, but fallback to entire body
        content_root = soup.find('main') or soup.find('article') or soup.find('body') or soup

        # 7. Convert to Markdown
        clean_html = str(content_root)
        markdown_text = self.html_converter.handle(clean_html)

        # 8. Clean up Markdown text (collapse whitespace, strip redundant empty lines)
        cleaned_markdown = self._clean_markdown(markdown_text)

        cleaned_chars = len(cleaned_markdown)
        reduction_pct = round(
            max(0.0, (original_chars - cleaned_chars) / max(1, original_chars)) * 100, 
            2
        )

        metadata = {
            "url": url,
            "original_chars": original_chars,
            "cleaned_chars": cleaned_chars,
            "token_reduction_pct": reduction_pct,
            "emails": list(emails),
            "phones": list(phones),
            "contact_pages": list(contact_pages),
            "linkedin_urls": list(linkedin_urls),
        }

        return cleaned_markdown, metadata

    def _extract_emails(self, soup: BeautifulSoup, raw_html: str) -> Set[str]:
        emails: Set[str] = set()

        # mailto links
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.lower().startswith('mailto:'):
                clean_mail = href[7:].split('?')[0].strip().strip("<>\"'").lstrip("u003e")
                if EMAIL_REGEX.match(clean_mail):
                    emails.add(clean_mail.lower())

        # Regex over text
        for match in EMAIL_REGEX.finditer(raw_html):
            candidate = match.group(0).lower().strip("<>\"'").lstrip("u003e")
            # Ignore dummy or template emails
            if not any(dummy in candidate for dummy in ['example.com', 'domain.com', 'email.com', 'yourcompany.com', '.png', '.jpg', '.webp']):
                if EMAIL_REGEX.match(candidate):
                    emails.add(candidate)

        return emails

    def _extract_phones(self, soup: BeautifulSoup, raw_html: str) -> Set[str]:
        phones: Set[str] = set()
        # tel: links
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.lower().startswith('tel:'):
                clean_phone = href[4:].split('?')[0].strip()
                digits_only = re.sub(r'\D', '', clean_phone)
                if 7 <= len(digits_only) <= 15:
                    phones.add(clean_phone)

        # Regex search over visible text (avoids internal JS integers/asset IDs)
        page_text = soup.get_text(separator=" ")
        for match in PHONE_REGEX.finditer(page_text):
            candidate = match.group(0).strip(" -.,")
            phones.add(candidate)

        return phones

    def _extract_contact_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        from urllib.parse import urljoin
        contact_links: Set[str] = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            text = a.get_text(strip=True).lower()
            href_lower = href.lower()
            if any(k in href_lower for k in ['/contact', '/support', '/sales', 'contact-us', 'contact-sales', 'contact_us']) or \
               any(k in text for k in ['contact us', 'contact sales', 'get in touch', 'reach us', 'support team']):
                if href.startswith("http://") or href.startswith("https://"):
                    contact_links.add(href.rstrip("/"))
                elif href.startswith("/"):
                    if base_url:
                        contact_links.add(urljoin(base_url, href).rstrip("/"))
        return contact_links

    def _extract_linkedin_urls(self, soup: BeautifulSoup, raw_html: str) -> Set[str]:
        urls: Set[str] = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if 'linkedin.com' in href:
                match = LINKEDIN_REGEX.search(href)
                if match:
                    urls.add(match.group(0).rstrip('/'))

        for match in LINKEDIN_REGEX.finditer(raw_html):
            urls.add(match.group(0).rstrip('/'))

        return urls

    def _clean_markdown(self, text: str) -> str:
        # Collapse multiple empty lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Collapse excessive inline spaces
        text = re.sub(r'[ \t]{2,}', ' ', text)
        # Remove lines that are just dashes or empty bullets
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped in ['*', '-', '_', '---', '***']:
                continue
            lines.append(line)
        return '\n'.join(lines).strip()
