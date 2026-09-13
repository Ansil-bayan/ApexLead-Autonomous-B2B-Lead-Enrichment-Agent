from __future__ import annotations
import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from core.models import ExtractedLeadIntelligence, LeadershipMember, TokenUsage

load_dotenv()
logger = logging.getLogger(__name__)

# Approximate pricing per 1M tokens in USD
MODEL_PRICING = {
    "gemini": {"input": 0.075, "output": 0.30},     # Gemini 1.5 / 2.5 Flash
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "groq": {"input": 0.050, "output": 0.080},
    "fallback": {"input": 0.0, "output": 0.0}
}


EXTRACTION_SYSTEM_PROMPT = """You are a specialized B2B intelligence analyst. Your job is to extract strict, highly accurate structured lead intelligence from scraped web content.

CRITICAL EXTRACTION RULES:
1. Company Overview: MUST be EXACTLY a concise 2-sentence summary of what the company does. No more, no less.
2. Target Audience / ICP: Clearly specify WHO their product is built for (e.g., "Software engineers and API developers building distributed web services").
3. Contact Points: Extract all public emails (e.g. contact@, sales@, support@, hello@, press@, info@), phone numbers, and official contact/sales URLs. Be thorough and include all discovered contact channels.
4. Key Leadership: Extract real executive, founder, and key leadership team member names, roles/titles (e.g. CEO, Co-Founder, CTO, Head of Product), and their LinkedIn URLs. Thoroughly check About, Team, and Company page sections for founder and leadership mentions.
5. Data Confidence Score: Provide a realistic float between 0.0 and 1.0 reflecting how comprehensive and reliable the discovered information is (e.g. 0.90 if overview, ICP, email, and leadership were clearly found; 0.50 if only basic marketing text was found).

OUTPUT FORMAT:
You must respond with valid JSON strictly adhering to this schema:
{
  "company_name": "string",
  "company_overview": "string (exactly 2 sentences)",
  "target_audience_icp": "string",
  "contact_points": ["email1@...", "email2@...", "+1 ...", "https://.../contact"],
  "key_leadership": [
    {"name": "Full Name", "role": "Title", "linkedin_url": "https://linkedin.com/in/... or null"}
  ],
  "data_confidence_score": 0.85
}
"""


class MissingAPIKeyError(ValueError):
    """Raised when no LLM API key is provided."""
    pass


class StructuredExtractor:
    """Multi-provider LLM extraction engine with token and cost tracking."""

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None):
        self.provider = provider or "gemini"
        
        # Use explicitly passed key or fallback to env
        self.gemini_key = (api_key.strip() if (self.provider == "gemini" and api_key) else os.getenv("GEMINI_API_KEY", "").strip())
        self.openai_key = (api_key.strip() if (self.provider == "openai" and api_key) else os.getenv("OPENAI_API_KEY", "").strip())
        self.groq_key = (api_key.strip() if (self.provider == "groq" and api_key) else os.getenv("GROQ_API_KEY", "").strip())

    def extract_intelligence(
        self,
        domain: str,
        content_markdown: str,
        pre_extracted_emails: List[str],
        pre_extracted_linkedin: List[str],
        pre_extracted_phones: Optional[List[str]] = None,
        pre_extracted_contact_pages: Optional[List[str]] = None
    ) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        """
        Extracts structured intelligence from markdown content using the configured LLM.
        Raises MissingAPIKeyError if no API key is provided.
        """
        prompt_content = self._build_prompt(
            domain=domain,
            content=content_markdown,
            emails=pre_extracted_emails,
            linkedin_links=pre_extracted_linkedin,
            phones=pre_extracted_phones or [],
            contact_pages=pre_extracted_contact_pages or []
        )

        # Auto-detect provider if user pasted an OpenAI or Groq key while on Gemini
        clean_key = (self.gemini_key or self.openai_key or self.groq_key).strip()
        if clean_key.startswith("sk-") and not clean_key.startswith("gsk_"):
            self.provider = "openai"
            self.openai_key = clean_key
        elif clean_key.startswith("gsk_"):
            self.provider = "groq"
            self.groq_key = clean_key
        elif clean_key.startswith("AIzaSy"):
            self.provider = "gemini"
            self.gemini_key = clean_key

        # Ensure API key is present for the requested provider
        if self.provider == "gemini":
            if not self.gemini_key:
                raise MissingAPIKeyError("No API key found. Please provide a GEMINI_API_KEY.")
            return self._extract_with_gemini(prompt_content)

        elif self.provider == "openai":
            if not self.openai_key:
                raise MissingAPIKeyError("No API key found. Please provide an OPENAI_API_KEY.")
            return self._extract_with_openai(prompt_content)

        elif self.provider == "groq":
            if not self.groq_key:
                raise MissingAPIKeyError("No API key found. Please provide a GROQ_API_KEY.")
            return self._extract_with_groq(prompt_content)

        else:
            raise MissingAPIKeyError(f"No API key found for provider '{self.provider}'. Please provide an API key.")

    def _build_prompt(
        self, 
        domain: str, 
        content: str, 
        emails: List[str], 
        linkedin_links: List[str],
        phones: Optional[List[str]] = None,
        contact_pages: Optional[List[str]] = None
    ) -> str:
        # Truncate content to ~60,000 characters to ensure full coverage of about, team, and contact pages
        truncated_content = content[:60000]
        context_hints = []
        if emails:
            context_hints.append(f"Pre-detected emails on site: {', '.join(emails)}")
        if phones:
            context_hints.append(f"Pre-detected phone numbers: {', '.join(phones)}")
        if contact_pages:
            context_hints.append(f"Pre-detected contact/sales pages: {', '.join(contact_pages[:4])}")
        if linkedin_links:
            context_hints.append(f"Pre-detected LinkedIn links on site: {', '.join(linkedin_links[:10])}")

        hints_text = "\n".join(context_hints)
        return (
            f"TARGET DOMAIN: {domain}\n\n"
            f"DISCOVERED CONTEXT HINTS:\n{hints_text}\n\n"
            f"CRAWLED PAGE CONTENT:\n"
            f"\"\"\"\n{truncated_content}\n\"\"\"\n\n"
            f"Extract the company intelligence now in strict JSON format."
        )

    def _extract_with_gemini(self, prompt: str) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        # Try SDK first with known models
        try:
            return self._extract_with_gemini_sdk(prompt)
        except Exception as sdk_err:
            logger.warning(f"Gemini SDK extraction encountered: {sdk_err}. Trying direct REST API...")
            try:
                return self._extract_with_gemini_rest(prompt)
            except Exception as rest_err:
                raise ValueError(f"Gemini API Error: {rest_err}") from sdk_err

    def _extract_with_gemini_sdk(self, prompt: str) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        
        # Valid official Gemini models in priority order
        env_model = os.getenv("GEMINI_MODEL", "").strip()
        if env_model in ("gemini-2.0-flash", "gemini-2.5-flash"):
            models_to_try = ["gemini-3.6-flash", env_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        elif env_model:
            models_to_try = [env_model, "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        else:
            models_to_try = [
                "gemini-3.6-flash",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ]
        seen = set()
        candidate_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        last_err = None
        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=EXTRACTION_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=ExtractedLeadIntelligence,
                        temperature=0.1,
                    )
                )

                resp_text = response.text.strip()
                if resp_text.startswith("```json"):
                    resp_text = resp_text[7:]
                if resp_text.startswith("```"):
                    resp_text = resp_text[3:]
                if resp_text.endswith("```"):
                    resp_text = resp_text[:-3]

                data_dict = json.loads(resp_text.strip())
                lead = ExtractedLeadIntelligence(**data_dict)

                prompt_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else len(prompt) // 4
                comp_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else len(response.text) // 4
                total_tokens = prompt_tokens + comp_tokens

                cost = (
                    (prompt_tokens / 1_000_000) * MODEL_PRICING["gemini"]["input"] +
                    (comp_tokens / 1_000_000) * MODEL_PRICING["gemini"]["output"]
                )

                return lead, TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=comp_tokens,
                    total_tokens=total_tokens,
                    estimated_cost_usd=round(cost, 6)
                )
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err

    def _extract_with_gemini_rest(self, prompt: str) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        import httpx

        env_model = os.getenv("GEMINI_MODEL", "").strip()
        if env_model in ("gemini-2.0-flash", "gemini-2.5-flash"):
            models_to_try = ["gemini-3.6-flash", env_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        elif env_model:
            models_to_try = [env_model, "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        else:
            models_to_try = [
                "gemini-3.6-flash",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ]
        seen = set()
        candidate_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        last_err = None
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": f"{EXTRACTION_SYSTEM_PROMPT}\n\n{prompt}"}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }

            try:
                with httpx.Client(timeout=35.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        cand = data.get("candidates", [{}])[0]
                        text_content = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
                        
                        cleaned_text = text_content.strip()
                        if cleaned_text.startswith("```json"):
                            cleaned_text = cleaned_text[7:]
                        if cleaned_text.startswith("```"):
                            cleaned_text = cleaned_text[3:]
                        if cleaned_text.endswith("```"):
                            cleaned_text = cleaned_text[:-3]

                        data_dict = json.loads(cleaned_text.strip())
                        lead = ExtractedLeadIntelligence(**data_dict)

                        usage_meta = data.get("usageMetadata", {})
                        prompt_tokens = usage_meta.get("promptTokenCount", len(prompt) // 4)
                        comp_tokens = usage_meta.get("candidatesTokenCount", len(text_content) // 4)
                        total_tokens = prompt_tokens + comp_tokens

                        cost = (
                            (prompt_tokens / 1_000_000) * MODEL_PRICING["gemini"]["input"] +
                            (comp_tokens / 1_000_000) * MODEL_PRICING["gemini"]["output"]
                        )

                        return lead, TokenUsage(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=comp_tokens,
                            total_tokens=total_tokens,
                            estimated_cost_usd=round(cost, 6)
                        )
                    else:
                        err_msg = resp.json().get("error", {}).get("message", resp.text)
                        last_err = f"Status {resp.status_code}: {err_msg}"
                        if resp.status_code == 404 or "not found" in err_msg.lower() or "no longer available" in err_msg.lower():
                            continue
                        raise ValueError(f"Status {resp.status_code}: {err_msg}")
            except Exception as e:
                last_err = str(e)
                if "not found" in str(e).lower() or "no longer available" in str(e).lower() or "404" in str(e):
                    continue
                raise e

        raise ValueError(f"All Gemini model endpoints failed. Last error: {last_err}")

    def _extract_with_openai(self, prompt: str) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        extracted_json = json.loads(content)
        lead = ExtractedLeadIntelligence(**extracted_json)

        usage_data = data.get("usage", {})
        p_tok = usage_data.get("prompt_tokens", len(prompt) // 4)
        c_tok = usage_data.get("completion_tokens", len(content) // 4)
        cost = (
            (p_tok / 1_000_000) * MODEL_PRICING["gpt-4o-mini"]["input"] +
            (c_tok / 1_000_000) * MODEL_PRICING["gpt-4o-mini"]["output"]
        )

        usage = TokenUsage(
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            estimated_cost_usd=round(cost, 6)
        )
        return lead, usage

    def _extract_with_groq(self, prompt: str) -> Tuple[ExtractedLeadIntelligence, TokenUsage]:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        extracted_json = json.loads(content)
        lead = ExtractedLeadIntelligence(**extracted_json)

        usage_data = data.get("usage", {})
        p_tok = usage_data.get("prompt_tokens", len(prompt) // 4)
        c_tok = usage_data.get("completion_tokens", len(content) // 4)
        cost = (
            (p_tok / 1_000_000) * MODEL_PRICING["groq"]["input"] +
            (c_tok / 1_000_000) * MODEL_PRICING["groq"]["output"]
        )

        usage = TokenUsage(
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            estimated_cost_usd=round(cost, 6)
        )
        return lead, usage
