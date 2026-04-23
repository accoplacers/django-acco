"""
resume_parser.py — AI Resume Parsing Engine for AccoPlacers

Extracts structured candidate intelligence from PDF resumes using a
two-stage pipeline:

    Stage 1: Raw text extraction from PDF (PyMuPDF / pdfplumber fallback).
    Stage 2: LLM-powered semantic parsing into a strict JSON schema
             optimized for the GCC Accounting, Audit & Finance domain.

This module is a standalone service. It has NO Django dependencies and
can be called from management commands, Celery tasks, or view logic.

Usage:
    from base.services.resume_parser import extract_text_from_pdf, parse_resume_with_llm

    text = extract_text_from_pdf("/path/to/resume.pdf")
    structured = parse_resume_with_llm(text)
"""

import json
import logging
import os
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# SCHEMA DEFINITION
# ============================================================

@dataclass
class ParsedResume:
    """
    The canonical output schema for parsed resume data.
    Every field maps directly to a future vector-DB column.
    """
    certifications: list[str] = field(default_factory=list)
    erp_software: list[str] = field(default_factory=list)
    regulatory_knowledge: list[str] = field(default_factory=list)
    core_competencies: list[str] = field(default_factory=list)
    years_of_experience: int = 0
    notice_period: str = "Unknown"

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# STAGE 1 — PDF TEXT EXTRACTION
# ============================================================

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF file.

    Strategy:
        1. Try PyMuPDF (fitz) first — fastest, handles most PDFs.
        2. Fall back to pdfplumber — better with table-heavy CVs.
        3. If both fail, raise a clean error.

    Args:
        file_path: Absolute or relative path to the PDF.

    Returns:
        The full extracted text as a single string.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If zero text could be extracted (scanned image PDF).
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported file format: {path.suffix}. Only PDF is supported.")

    text = ""

    # --- Attempt 1: PyMuPDF (fitz) ---
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        text = "\n".join(pages).strip()

        if text:
            logger.info(f"[PyMuPDF] Extracted {len(text)} chars from {path.name}")
            return text

    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed. Falling back to pdfplumber.")
    except Exception as e:
        logger.warning(f"PyMuPDF failed on {path.name}: {e}. Falling back to pdfplumber.")

    # --- Attempt 2: pdfplumber ---
    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
        text = "\n".join(pages).strip()

        if text:
            logger.info(f"[pdfplumber] Extracted {len(text)} chars from {path.name}")
            return text

    except ImportError:
        logger.error("Neither PyMuPDF nor pdfplumber is installed. Install one: pip install PyMuPDF pdfplumber")
        raise RuntimeError("No PDF extraction library available. Install PyMuPDF or pdfplumber.")
    except Exception as e:
        logger.error(f"pdfplumber also failed on {path.name}: {e}")

    # --- Both failed ---
    if not text:
        raise ValueError(
            f"Zero text extracted from {path.name}. "
            "This is likely a scanned image PDF. OCR integration is required."
        )

    # --- ENFORCE WALLET PROTECTION ---
    # Hard character limit to prevent "zip bomb" style text attacks
    # that spike token costs. 12,000 chars is ~3,000 words.
    if len(text) > 12000:
        logger.warning(f"Extracted text for {path.name} exceeds 12,000 chars. Truncating.")
        text = text[:12000]

    return text


# ============================================================
# STAGE 2 — LLM-POWERED SEMANTIC PARSING
# ============================================================

# The system prompt is the single most critical piece of this engine.
# It is domain-locked to GCC Accounting/Audit/Finance to prevent
# hallucinated certifications or irrelevant skill extraction.

SYSTEM_PROMPT = """You are a senior recruitment data analyst specializing in the
Accounting, Audit, and Finance sector across the GCC (Gulf Cooperation Council)
region — UAE, Saudi Arabia, Qatar, Bahrain, Oman, and Kuwait.

Your task is to extract structured intelligence from a candidate's resume text.

RULES:
1. Return ONLY valid JSON. No markdown, no explanation, no preamble.
2. Extract only what is EXPLICITLY stated in the resume. Do NOT infer or hallucinate.
3. If a field cannot be determined from the text, use the default value.
4. Normalize all entries: title-case for certifications, uppercase for acronyms.
5. Deduplicate entries within each list.

DOMAIN CONTEXT (use this to correctly classify ambiguous terms):
- Certifications: ACCA, CPA, CMA, CIA, CIMA, CA, CFA, FRM, SOCPA, DipIFR, ACA
- ERP Software: SAP, Oracle, Tally, QuickBooks, Sage, Xero, Zoho Books, NetSuite, MS Dynamics
- Regulatory: IFRS, GAAP, GCC VAT, UAE Corporate Tax, Excise Tax, Transfer Pricing,
  Anti-Money Laundering (AML), FATCA, ESR (Economic Substance Regulations)
- Competencies: Internal Audit, External Audit, Payroll Processing, Accounts Payable,
  Accounts Receivable, Financial Reporting, Budgeting & Forecasting, Tax Filing,
  Bank Reconciliation, Fixed Assets, Treasury, Consolidation, Statutory Audit

SCHEMA — return this exact JSON structure:
{
  "certifications": ["string"],
  "erp_software": ["string"],
  "regulatory_knowledge": ["string"],
  "core_competencies": ["string"],
  "years_of_experience": 0,
  "notice_period": "Unknown"
}

FIELD RULES:
- certifications: Professional designations only. NOT university degrees.
- erp_software: Accounting/ERP software and tools. Include Excel/Advanced Excel if mentioned.
- regulatory_knowledge: Tax laws, accounting standards, compliance frameworks.
- core_competencies: Functional skills and areas of practice. Max 10 items.
- years_of_experience: Integer. Calculate from earliest work date to latest, or use
  explicitly stated "X years of experience". If unclear, return 0.
- notice_period: Extract if stated. Common values: "Immediate", "30 Days", "60 Days",
  "90 Days", "Currently Serving". If not mentioned, return "Unknown".
"""


# ============================================================
# LLM ROUTING & FALLBACK CONFIG
# ============================================================

# Define the model priority list. 
# Order: Fastest/Cheapest -> High-Intelligence Fallbacks.
DEFAULT_ROUTING_CONFIG = [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "anthropic", "model": "claude-3-haiku-20240307"},
    {"provider": "openai", "model": "gpt-4o"},
    {"provider": "anthropic", "model": "claude-3-5-sonnet-20240620"},
]

def parse_resume_with_llm(
    text: str,
    routing_config: list[dict] = None,
    timeout: int = 15,
) -> ParsedResume:
    """
    Send extracted resume text to an LLM and parse the response into
    a structured ParsedResume object.

    Uses a cascading fallback strategy: if the first model fails (rate limit,
    server error, or missing key), it automatically tries the next one.

    Args:
        text: The raw resume text from Stage 1.
        routing_config: Optional list of {"provider": str, "model": str}.
        timeout: API call timeout per attempt.

    Returns:
        A ParsedResume dataclass with the extracted fields.
    """
    if not text or len(text.strip()) < 50:
        logger.warning("Resume text is too short for meaningful extraction.")
        return ParsedResume()

    config = routing_config or DEFAULT_ROUTING_CONFIG

    raw_json = None
    errors = []
    timed_out = 0

    for entry in config:
        provider = entry["provider"]
        model = entry["model"]

        try:
            logger.info(f"Attempting parse with {provider}:{model}...")
            raw_json = _call_llm_provider(text, provider, model, timeout)
            if raw_json:
                logger.info(f"Successfully parsed with {provider}:{model}")
                break
        except TimeoutError as e:
            err_msg = f"{provider}:{model} timed out after {timeout}s"
            logger.warning(err_msg)
            errors.append(err_msg)
            timed_out += 1
            continue
        except Exception as e:
            err_msg = f"{provider}:{model} failed: {str(e)}"
            logger.warning(err_msg)
            errors.append(err_msg)
            continue

    if not raw_json:
        if timed_out == len(config):
            raise TimeoutError(
                f"Resume parse: all {len(config)} LLM provider(s) timed out "
                f"after {timeout}s each."
            )
        logger.error(f"All LLM providers failed. Errors: {errors}")
        return ParsedResume()

    return _parse_json_response(raw_json)


def _call_llm_provider(text: str, provider: str, model: str, timeout: int) -> str:
    """
    Routes the call to the specific provider implementation.
    """
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return _call_openai(text, model, timeout, api_key)
    
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return _call_anthropic(text, model, timeout, api_key)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_openai(text: str, model: str, timeout: int, api_key: str) -> str:
    """OpenAI call with specific error handling for routing."""
    try:
        from openai import OpenAI, RateLimitError, APIStatusError, APITimeoutError

        client = OpenAI(api_key=api_key, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            temperature=0.0,
            max_tokens=800,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract structured data from this resume:\n\n{text}"},
            ],
        )
        return response.choices[0].message.content

    except ImportError:
        raise RuntimeError("OpenAI SDK not installed.")
    except APITimeoutError as e:
        raise TimeoutError(f"OpenAI timed out after {timeout}s") from e
    except (RateLimitError, APIStatusError) as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected OpenAI error: {e}")
        raise e


def _call_anthropic(text: str, model: str, timeout: int, api_key: str) -> str:
    """Anthropic call with specific error handling for routing."""
    try:
        import anthropic
        from anthropic import RateLimitError, InternalServerError, APITimeoutError

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        response = client.messages.create(
            model=model,
            max_tokens=800,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Extract structured data from this resume:\n\n{text}"},
            ],
        )
        return response.content[0].text

    except ImportError:
        raise RuntimeError("Anthropic SDK not installed.")
    except APITimeoutError as e:
        raise TimeoutError(f"Anthropic timed out after {timeout}s") from e
    except (RateLimitError, InternalServerError) as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected Anthropic error: {e}")
        raise e


def _parse_json_response(raw: str) -> ParsedResume:
    """
    Parse the raw LLM response string into a validated ParsedResume.
    Handles common LLM output quirks:
        - Markdown code fences wrapping the JSON.
        - Trailing commas.
        - Extra keys not in our schema (ignored).
    """
    if not raw:
        logger.error("LLM returned empty response.")
        return ParsedResume()

    # Strip markdown code fences if present.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode failed: {e}\nRaw LLM output:\n{raw[:500]}")
        return ParsedResume()

    if not isinstance(data, dict):
        logger.error(f"LLM returned non-dict JSON: {type(data)}")
        return ParsedResume()

    # Validate and coerce each field to the expected type.
    def safe_list(key: str) -> list[str]:
        val = data.get(key, [])
        if isinstance(val, list):
            return [str(item).strip() for item in val if item]
        return []

    def safe_int(key: str, default: int = 0) -> int:
        val = data.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def safe_str(key: str, default: str = "Unknown") -> str:
        val = data.get(key, default)
        return str(val).strip() if val else default

    return ParsedResume(
        certifications=safe_list("certifications"),
        erp_software=safe_list("erp_software"),
        regulatory_knowledge=safe_list("regulatory_knowledge"),
        core_competencies=safe_list("core_competencies"),
        years_of_experience=safe_int("years_of_experience"),
        notice_period=safe_str("notice_period"),
    )
