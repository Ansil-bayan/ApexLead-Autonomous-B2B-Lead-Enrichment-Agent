import unittest
from core.preprocessor import ContentPreprocessor

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Acme Corp - Scalable Cloud Infrastructure</title>
    <style>body { background: red; } .hero { font-size: 20px; }</style>
    <script>console.log("tracking pixel");</script>
</head>
<body>
    <div class="cookie-consent-modal">We use cookies. Accept here.</div>
    <header>
        <svg height="100" width="100"><circle cx="50" cy="50" r="40" stroke="green" /></svg>
        <nav><a href="/">Home</a> | <a href="/about">About Us</a></nav>
    </header>
    <main>
        <h1>Welcome to Acme Cloud</h1>
        <p>Acme provides hyper-scalable database infrastructure for real-time applications. Our automated platform handles multi-region replication and failover seamlessly.</p>
        <p>For sales inquiries, email us at <a href="mailto:sales@acmecloud.io">sales@acmecloud.io</a> or support@acmecloud.io.</p>
        <div class="team">
            <h2>Leadership</h2>
            <p>Jane Doe - Chief Executive Officer. Connect on <a href="https://www.linkedin.com/in/janedoe-ceo">LinkedIn</a>.</p>
        </div>
    </main>
    <footer>
        <p>&copy; 2026 Acme Corp. All rights reserved.</p>
    </footer>
</body>
</html>
"""

class TestContentPreprocessor(unittest.TestCase):
    def setUp(self):
        self.preprocessor = ContentPreprocessor()

    def test_noise_removal_and_token_reduction(self):
        markdown, meta = self.preprocessor.process_html(SAMPLE_HTML, url="https://acmecloud.io")
        
        # Verify scripts, styles, SVGs, and cookie modals are removed
        self.assertNotIn("console.log", markdown)
        self.assertNotIn("background: red", markdown)
        self.assertNotIn("<circle", markdown)
        self.assertNotIn("cookie-consent-modal", markdown)

        # Verify key semantic content is preserved
        self.assertIn("Acme provides hyper-scalable database infrastructure", markdown)
        self.assertIn("Jane Doe", markdown)

        # Verify token reduction calculation
        self.assertGreater(meta["token_reduction_pct"], 40.0)
        self.assertLess(meta["cleaned_chars"], meta["original_chars"])

    def test_email_and_linkedin_extraction(self):
        markdown, meta = self.preprocessor.process_html(SAMPLE_HTML, url="https://acmecloud.io")
        
        emails = meta["emails"]
        linkedin_urls = meta["linkedin_urls"]

        self.assertIn("sales@acmecloud.io", emails)
        self.assertIn("support@acmecloud.io", emails)
        self.assertTrue(any("janedoe-ceo" in u for u in linkedin_urls))

    def test_phone_and_contact_url_extraction(self):
        html_with_contacts = """
        <html><body>
            <p>Call us at <a href="tel:+18005550199">(800) 555-0199</a> or visit our <a href="/contact-sales">Contact Sales</a> page.</p>
        </body></html>
        """
        _, meta = self.preprocessor.process_html(html_with_contacts, url="https://acmecloud.io")
        self.assertTrue(any("800" in p and "555" in p for p in meta["phones"]))
        self.assertTrue(any("contact-sales" in u for u in meta["contact_pages"]))

if __name__ == "__main__":
    unittest.main()
