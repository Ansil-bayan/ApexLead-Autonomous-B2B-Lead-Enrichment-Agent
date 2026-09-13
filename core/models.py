from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class LeadershipMember(BaseModel):
    name: str = Field(..., description="Full name of the executive, founder, or key team member")
    role: str = Field(..., description="Role or title (e.g., CEO, Co-Founder, CTO, VP of Product)")
    linkedin_url: Optional[str] = Field(
        default=None, 
        description="Public LinkedIn profile URL if discovered directly or through external search"
    )


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(default=0, description="Tokens used in the LLM input prompt")
    completion_tokens: int = Field(default=0, description="Tokens used in the LLM output completion")
    total_tokens: int = Field(default=0, description="Total tokens consumed")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")


class ExtractedLeadIntelligence(BaseModel):
    """Pydantic model used for strict LLM structured output parsing."""
    company_name: str = Field(..., description="Official brand/company name")
    company_overview: str = Field(
        ..., 
        description="A concise 2-sentence summary of what the company does"
    )
    target_audience_icp: str = Field(
        ..., 
        description="Who their product is built for (Ideal Customer Profile, e.g., 'Developers building backend applications')"
    )
    contact_points: List[str] = Field(
        default_factory=list, 
        description="Generic or public emails found on the site (e.g. contact@, sales@, support@, hello@)"
    )
    key_leadership: List[LeadershipMember] = Field(
        default_factory=list, 
        description="Names, roles/titles, and LinkedIn profile URLs of key leadership/founders"
    )
    data_confidence_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Estimated confidence score between 0.0 and 1.0 indicating the quality and completeness of the extracted data"
    )


class EnrichedLead(BaseModel):
    """Full lead enrichment record including crawl sources and cost tracking."""
    domain: str = Field(..., description="Target domain, e.g. postman.com")
    company_name: str = Field(..., description="Official brand/company name")
    company_overview: str = Field(..., description="Concise 2-sentence summary of what they do")
    target_audience_icp: str = Field(..., description="Ideal Customer Profile / target audience")
    contact_points: List[str] = Field(default_factory=list, description="Public emails found")
    key_leadership: List[LeadershipMember] = Field(default_factory=list, description="Key leadership & LinkedIn URLs")
    data_confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    sources_crawled: List[str] = Field(default_factory=list, description="List of URLs crawled for this domain")
    cost_metrics: TokenUsage = Field(default_factory=TokenUsage, description="Token usage and cost breakdown")
    external_search_used: bool = Field(default=False, description="Whether search fallback was utilized to find leadership links")
    error: Optional[str] = Field(default=None, description="Error message if domain enrichment partially or fully failed")
