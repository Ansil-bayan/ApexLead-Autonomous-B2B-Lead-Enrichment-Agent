import unittest
from core.models import LeadershipMember, ExtractedLeadIntelligence, EnrichedLead, TokenUsage
from core.crawler import PlaywrightCrawler

SAMPLE_HOMEPAGE_HTML = """
<html>
<body>
    <a href="/about">About Postman</a>
    <a href="/pricing">Pricing Plans</a>
    <a href="/team">Our Leadership</a>
    <a href="https://external-blog.com/news">External Blog</a>
    <a href="mailto:info@domain.com">Email Us</a>
    <a href="#section-feature">Jump</a>
</body>
</html>
"""

class TestCrawlerAndModels(unittest.TestCase):
    def test_pydantic_models(self):
        member = LeadershipMember(name="Abhinav Asthana", role="CEO", linkedin_url="https://linkedin.com/in/abhinavasthana")
        self.assertEqual(member.name, "Abhinav Asthana")
        self.assertEqual(member.role, "CEO")

        lead = ExtractedLeadIntelligence(
            company_name="Postman",
            company_overview="Postman is an API platform. It simplifies API development.",
            target_audience_icp="API developers and engineering teams",
            contact_points=["contact@postman.com"],
            key_leadership=[member],
            data_confidence_score=0.92
        )
        self.assertEqual(lead.company_name, "Postman")
        self.assertAlmostEqual(lead.data_confidence_score, 0.92)

    def test_subpage_discovery(self):
        crawler = PlaywrightCrawler()
        discovered = crawler.discover_subpages(SAMPLE_HOMEPAGE_HTML, "https://postman.com", "postman.com")
        
        # Verify internal subpages discovered and external/mailto links filtered out
        self.assertTrue(any("/about" in url for url in discovered))
        self.assertTrue(any("/team" in url for url in discovered))
        self.assertFalse(any("external-blog.com" in url for url in discovered))
        self.assertFalse(any("mailto:" in url for url in discovered))

if __name__ == "__main__":
    unittest.main()
