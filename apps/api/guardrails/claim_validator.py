"""
Claim Grounding Validator.

Validates that claims in generated resumes are grounded in source material.
Detects potentially hallucinated achievements, companies, metrics, and titles.
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ClaimType(Enum):
    """Types of claims that can be validated."""
    QUANTIFIED = "quantified"  # Numbers, percentages, metrics
    COMPANY = "company"  # Company names
    TITLE = "title"  # Job titles
    SKILL = "skill"  # Technical skills
    TIMEFRAME = "timeframe"  # Years of experience


@dataclass
class UngroundedClaim:
    """Represents a potentially ungrounded claim."""
    claim: str
    claim_type: ClaimType
    confidence: float  # 0-1, higher = more confident this is ungrounded
    context: str = ""  # Surrounding text for context


def extract_quantified_claims(text: str) -> list[tuple[str, str]]:
    """
    Extract quantified claims from text.

    Returns list of (claim_text, full_match) tuples.
    """
    patterns = [
        # Percentages with context
        (r"(\d+(?:\.\d+)?%\s+(?:increase|decrease|improvement|reduction|growth|savings?))", "percentage"),
        # Dollar amounts
        (r"(\$[\d,]+(?:\.\d{2})?(?:[KMB]|k|m|b)?(?:\s+(?:in\s+)?(?:revenue|savings|cost|budget|funding))?)", "currency"),
        # Multipliers
        (r"(\d+(?:\.\d+)?x\s+(?:improvement|increase|growth|faster|better))", "multiplier"),
        # Large numbers with context
        (r"((?:over\s+)?\d{1,3}(?:,\d{3})+(?:\+)?\s+(?:users?|customers?|employees?|transactions?|requests?))", "count"),
        # Years of experience
        (r"(\d+\+?\s+years?\s+(?:of\s+)?experience)", "experience"),
        # Team/people counts
        (r"((?:team|group|department)\s+of\s+\d+(?:\+)?)", "team_size"),
        (r"((?:led|managed|mentored|supervised)\s+(?:a\s+)?(?:team\s+of\s+)?\d+(?:\+)?)", "leadership"),
    ]

    claims = []
    for pattern, claim_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claims.append((match.group(1), claim_type))

    return claims


def extract_company_names(text: str) -> list[str]:
    """
    Extract company names from text.

    Looks for patterns like "at Company", "for Company", "with Company".
    """
    patterns = [
        r"(?:at|for|with|joined|left)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})",
        r"(?:worked\s+(?:at|for))\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})",
    ]

    companies = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            company = match.group(1).strip()
            # Filter out common words that aren't companies
            if company.lower() not in {"the", "a", "an", "my", "our", "their"}:
                companies.append(company)

    return list(set(companies))


def extract_job_titles(text: str) -> list[str]:
    """
    Extract job titles from text.

    Looks for patterns like "as a Senior Engineer" or common title formats.
    """
    # Common title prefixes and roles
    title_patterns = [
        r"(?:as\s+(?:a\s+)?)((?:Senior|Junior|Lead|Staff|Principal|Chief)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"((?:VP|Director|Manager|Engineer|Developer|Analyst|Designer|Architect)\s+(?:of\s+)?[A-Za-z]+)",
        r"([A-Z][a-z]+\s+(?:Engineer|Developer|Manager|Director|Lead|Analyst))",
    ]

    titles = []
    for pattern in title_patterns:
        for match in re.finditer(pattern, text):
            titles.append(match.group(1).strip())

    return list(set(titles))


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Lowercase, remove extra whitespace, normalize numbers
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    # Normalize number formats: 1,000 -> 1000
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    return text


def find_number_in_source(number: str, source_text: str) -> bool:
    """Check if a number appears in source text, with some flexibility."""
    # Normalize the number
    num_clean = re.sub(r'[,\s]', '', number)

    # Try exact match
    if num_clean in source_text:
        return True

    # Try with common variations (e.g., 50 vs 50%)
    try:
        num_val = int(re.sub(r'[^\d]', '', num_clean))
        # Check if the number appears in source
        if str(num_val) in source_text:
            return True
        # Check for nearby values (within 10%)
        for variation in [str(int(num_val * 0.9)), str(int(num_val * 1.1))]:
            if variation in source_text:
                return True
    except ValueError:
        pass

    return False


def validate_claims_grounded(
    generated_resume: str,
    source_profile: str,
    source_discoveries: list[str] | None = None,
    confidence_threshold: float = 0.6
) -> list[UngroundedClaim]:
    """
    Check if claims in generated resume are grounded in source material.

    Args:
        generated_resume: The AI-generated resume text
        source_profile: The original user profile/resume
        source_discoveries: Optional list of discovery conversation answers
        confidence_threshold: Minimum confidence to report (0-1)

    Returns:
        List of potentially ungrounded claims above the confidence threshold.
    """
    ungrounded = []

    # Combine and normalize all source material
    source_parts = [source_profile or ""]
    if source_discoveries:
        source_parts.extend(source_discoveries)
    source_text = normalize_text(" ".join(source_parts))

    # Check quantified claims
    quantified_claims = extract_quantified_claims(generated_resume)
    for claim_text, claim_subtype in quantified_claims:
        # Extract numbers from the claim
        numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', claim_text)

        grounded = False
        for num in numbers:
            if find_number_in_source(num, source_text):
                grounded = True
                break

        if not grounded and numbers:
            # Higher confidence for specific metrics
            confidence = 0.8 if claim_subtype in ["percentage", "currency"] else 0.7

            if confidence >= confidence_threshold:
                ungrounded.append(UngroundedClaim(
                    claim=claim_text,
                    claim_type=ClaimType.QUANTIFIED,
                    confidence=confidence,
                    context=f"[{claim_subtype}]"
                ))

    # Check company names
    companies = extract_company_names(generated_resume)
    for company in companies:
        company_lower = company.lower()
        if company_lower not in source_text and len(company) > 3:
            # Check for partial matches (e.g., "Google" in "Google Inc.")
            if not any(company_lower in part for part in source_text.split()):
                confidence = 0.75
                if confidence >= confidence_threshold:
                    ungrounded.append(UngroundedClaim(
                        claim=f"Worked at {company}",
                        claim_type=ClaimType.COMPANY,
                        confidence=confidence,
                        context=""
                    ))

    # Check job titles (lower confidence as these may be paraphrased)
    titles = extract_job_titles(generated_resume)
    for title in titles:
        title_lower = title.lower()
        # Check if main keywords appear in source
        title_words = set(title_lower.split())
        source_words = set(source_text.split())

        # If less than half the title words appear in source, flag it
        overlap = len(title_words & source_words)
        if overlap < len(title_words) / 2:
            confidence = 0.5  # Lower confidence for titles
            if confidence >= confidence_threshold:
                ungrounded.append(UngroundedClaim(
                    claim=f"Title: {title}",
                    claim_type=ClaimType.TITLE,
                    confidence=confidence,
                    context=""
                ))

    if ungrounded:
        logger.warning(f"Found {len(ungrounded)} potentially ungrounded claims")

    return ungrounded


def format_ungrounded_claims(claims: list[UngroundedClaim]) -> list[dict]:
    """Format ungrounded claims for API response."""
    return [
        {
            "claim": c.claim,
            "type": c.claim_type.value,
            "confidence": c.confidence,
            "context": c.context,
            "message": f"'{c.claim}' may not be supported by your profile. Please verify."
        }
        for c in claims
    ]


def has_high_risk_claims(claims: list[UngroundedClaim], threshold: float = 0.8) -> bool:
    """
    Check if there are high-confidence ungrounded claims.

    Use this to decide if output should be flagged for review.
    """
    return any(c.confidence >= threshold for c in claims)
