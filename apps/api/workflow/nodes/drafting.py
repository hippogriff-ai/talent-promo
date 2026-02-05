"""Drafting node for generating ATS-friendly resume with suggestions."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import (
    ResumeState,
    DraftingSuggestion,
    DraftVersion,
    DraftValidationResult,
)
from guardrails import validate_output

logger = logging.getLogger(__name__)

settings = get_settings()


def _extract_content_from_code_block(content: str, language: str = "json") -> str:
    """Extract content from LLM response wrapped in markdown code blocks.

    Args:
        content: Raw LLM response that may be wrapped in code fences
        language: Expected language (e.g., 'json', 'html')

    Returns:
        Extracted content without code fences
    """
    lang_marker = f"```{language}"
    if lang_marker in content:
        content = content.split(lang_marker)[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return content.strip()


def get_llm(temperature: float = 0.3):
    """Get configured LLM for resume drafting."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        max_tokens=4096,
    )


RESUME_DRAFTING_PROMPT = """You are an elite resume writer. Your sole job: get this person an interview.

53% of hiring managers have reservations about AI-generated resumes. 33.5% spot them in under 20 seconds. Authenticity is your competitive advantage.

CORE PRINCIPLES (in priority order):

1. FAITHFUL — overrides everything else
   - NEVER merge distinct experience scopes ("6yr backend + 1yr AI" stays separate, never "7yr AI")
   - NEVER invent metrics not in the source material
   - Reframing WORDING is fine; reframing SCOPE, SCALE, or TIMEFRAME is fabrication
   - If the source says "helped with" do not upgrade to "led" or "drove"
   - NEVER attribute employer's scale to the candidate's individual work.
     The company may serve millions, but the candidate's specific project may serve a team of 23.
     Only use scale language ("serving millions", "at scale") if the source explicitly says
     the candidate's own work operates at that scale.
   - BAD: Source says "1 year ML side projects" → resume says "6+ years AI/ML experience"
   - BAD: Source says "contributed to migration" → resume says "Led migration"
   - BAD: Employer serves 2M users → summary says "serving 2M users" (that's the company, not the candidate)
   - NEVER add technologies/tools the candidate doesn't mention in their source material.
     If the job says "Kubernetes" but the source only mentions Docker, write "Docker" not "Kubernetes".
     Only include tools actually listed in the candidate's profile/resume.
   - GOOD: Source says "built internal tool" → resume says "Built internal automation tool"
   - GOOD: Source says "company serves 2M users" + candidate "built search feature" → "Built search feature for legal platform"

2. CONCISE — every bullet MUST be under 15 words, no exceptions
   - One achievement per bullet. Never join two ideas with "and", "while", or "resulting in"
   - Use the XYZ formula: "Accomplished [X] as measured by [Y] by doing [Z]"
   - BAD: "Led migration to microservices while mentoring 3 engineers and cutting deploy time 75%" (3 ideas)
   - GOOD: "Cut deploy time 75% via microservices migration" (8 words, 1 idea)
   - GOOD: "Mentored 3 junior engineers to production readiness" (7 words, 1 idea)
   - Professional summary: 2-3 sentences, under 40 words total

3. HIERARCHY-PRESERVING — respect the candidate's story
   - Keep their most prominent experience most prominent
   - Do NOT reorder roles to chase job keywords
   - Lead each role with THEIR strongest achievement, not what the job posting wants most
   - The candidate's identity comes through; this is THEIR resume, not a keyword-matching exercise

4. FOCUSED — depth over breadth, with job-specific evidence
   - Identify the top 3-5 job requirements. For EACH, include at least one bullet with specific evidence.
   - A resume that strongly matches 4 requirements beats one that weakly touches 10
   - Where the candidate has matching experience, use the job posting's technology names
     (e.g., if both the candidate and job mention containers, prefer "Kubernetes" from the job posting)
     But NEVER add technologies the candidate doesn't actually use — that violates FAITHFUL.
   - Include ALL metrics and numbers from the source material — percentages, team sizes, user counts, timeframes.
     If the source says "reduced latency 40%", include that. If it says "team of 5", include that.
   - If no metric exists in the source, DON'T INVENT ONE. A specific-but-unquantified bullet
     ("Built caching layer using Redis" — 6 words, named tech) is better than a fabricated number.
   - When the candidate matches only 3-4 of many requirements, write ONLY to those 3-4 with deep evidence.
     Do NOT fabricate or stretch bullets for non-matching requirements. Silence is better than a weak claim.
     A focused specialist always beats a stretched generalist.
   - For each matched requirement, provide the STRONGEST available evidence: named technology + specific
     outcome or context. One deeply-evidenced bullet per requirement is the minimum bar.
   - Maintain a coherent narrative (one story about who this person is)
   - BAD: "Experienced in cloud computing and DevOps practices" (no evidence, vague)
   - BAD: Inventing "serving 50M users" when the source doesn't mention that scale
   - BAD: Scattering unrelated keywords across bullets to touch every requirement
   - BAD: Writing bullets for requirements the candidate has NO matching experience for
   - GOOD: "Cut deploy time from 2hr to 15min using GitHub Actions + Docker" (source metric + job tech)
   - GOOD: "Built caching layer with Redis for product search" (specific, names tech, no invented metric)
   - GOOD: Ignoring 6 requirements to deeply address 4 matching ones

5. POLISHED — sound human, not AI
   - Zero filler: no "various", "multiple", "diverse", "dynamic", "robust", "innovative"
   - Zero AI-tells: no "spearheaded", "orchestrated", "revolutionized", "leveraged", "delve",
     "seamless", "holistic", "synergy", "utilize", "cutting-edge", "pivotal", "streamline"
   - NEVER use these phrases: "proven track record", "results-driven", "passionate about",
     "dynamic team player", "exceptional communication". These are the #1 AI fingerprint.
   - Zero passive voice: no "was responsible for", "was involved in"
   - Use plain strong verbs: Built, Led, Cut, Grew, Shipped, Fixed, Designed, Launched
   - NEVER use em dashes (—) or en dashes (–). Use commas, colons, or rewrite the sentence.
     Em dashes are the #1 typographic AI fingerprint.
     BAD: "Led migration — reducing deploy time 75%"
     GOOD: "Led migration, reducing deploy time 75%"
   - Vary bullet opening verbs. NEVER start 3+ bullets with the same word.
     BAD: "Built API… Built caching… Built monitoring…"
     GOOD: "Built API… Designed caching… Launched monitoring…"
   - Vary bullet rhythm: mix short punchy bullets (5-7 words) with longer ones (12-15 words).
     If 3+ consecutive bullets have the same word count, rewrite one shorter or longer.

AUTHENTICITY MARKERS — include these when the source material supports them:
- Before/after context for metrics: "from 3.2s to 0.8s" not just "reduced 75%"
- Constraints and trade-offs: "despite legacy codebase", "within 3-month deadline"
  (Only include if the source mentions them — NEVER invent constraints)
- Specific details only the candidate would know: "tool used by 23 team members daily"
- Named technologies, not categories: "Redis" not "caching solution", "React" not "frontend framework"
- These details signal truth because they're hard to fake.

SENIORITY POSITIONING:
- Senior/Director: Strategic impact, team size, business outcomes
- Mid-level: Balance individual contributions with collaboration
- Entry/Junior: Learning velocity, concrete project results, specific technologies
  (never use "spearheaded cross-functional strategy" for entry-level — scope must match seniority)

GAP HANDLING:
- Connect adjacent experience to requirements using WORDING only
- GOOD: "Built data pipelines in Python" (if they did build data pipelines)
- BAD: "Led enterprise AI initiatives" (if they did Python scripting, not AI leadership)
- When a gap is real, leave it out. Better to be honest than to stretch.
- Use TRANSFERABLE SKILLS to bridge gaps: if the gap analysis identifies a skill as transferable,
  reframe the candidate's existing experience using that angle. E.g., "project coordination" transfers
  to "program management" — but only if the source material supports the underlying experience.
- Use POTENTIAL CONCERNS to inoculate: if a concern is flagged (e.g., short tenure, career gap,
  industry switch), address it through framing rather than hiding it. E.g., for a career gap,
  highlight freelance/learning during that period if the source mentions it.

USER STYLE PREFERENCES (apply if provided):
- Tone: formal/conversational/confident/humble
- Structure: bullets/paragraphs/mixed
- First person: whether to use "I" statements
- Quantification: heavy_metrics/qualitative/balanced

OUTPUT FORMAT (HTML for Tiptap editor):

<h1>[Candidate Name]</h1>
<p>[Contact info: email | phone | location | LinkedIn]</p>

<h2>Professional Summary</h2>
<p>[2-3 sentences, under 40 words. Formula: "[Role] with [N] years [THEIR actual core expertise — NOT the target job's domain]. [Best metric achievement]. [What they bring to THIS role]."
CRITICAL: [N] years must match their ACTUAL years in that specific domain, not total career years.
BAD: "8+ years building AI-powered products" when source shows 8yr SWE + 1yr AI.
GOOD: "Full-stack engineer with 8 years of software development. Shipped AI assistant from POC to production in one week."
Be specific, not generic.]</p>

<h2>Experience</h2>
<h3>[Job Title] | [Company] | [Dates]</h3>
<ul>
<li>[Under 15 words. XYZ: Accomplished X, measured by Y, by doing Z]</li>
<li>[3-5 bullets per role. Most recent role gets most detail.]</li>
</ul>

<h2>Education</h2>
<p><strong>[Degree]</strong> - [Institution], [Year]</p>

<h2>Skills</h2>
<p>[Group by category: Languages: Python, Go, TypeScript | Frameworks: React, FastAPI | Cloud: AWS, GCP. Prioritize by relevance to target job.]</p>

<h2>Certifications</h2>
<ul>
<li>[Certification name — only if relevant]</li>
</ul>

BEFORE OUTPUTTING, verify each:
1. FIDELITY: Every claim traceable to source material. No merged scopes. No invented metrics.
2. SCALE ATTRIBUTION: Summary years match actual domain years (not total career). No employer-scale claims on individual work.
3. CONCISENESS: Every bullet under 15 words. No compound bullets. Summary under 40 words.
4. HIERARCHY: Candidate's most prominent role is still most prominent. Top achievements lead.
5. COHERENCE: Resume tells one clear story. Not scattered keyword coverage.
6. FOCUS: Top 3-5 requirements addressed deeply. Others left alone.
7. ACTION VERBS: Every bullet starts with a strong verb (Built, Led, Cut, Grew, Shipped, etc.)
8. HUMAN VOICE: No AI-tell words. No filler. No em dashes. Varied rhythm. Varied bullet openings (no 3+ starting with same verb). 3-5 bullets per role. Include before/after context and constraints where the source supports them.
9. SENIORITY: Language matches candidate's level. Entry-level doesn't say "led cross-functional strategy."

Output clean HTML only. No markdown. No code fences."""


SUGGESTION_GENERATION_PROMPT = """You are an expert resume consultant. 53% of hiring managers distrust AI-generated resumes.

Review this resume draft and generate 3-5 specific improvements. Prioritize:
1. Adding before/after context to metrics ("reduced from 3.2s to 0.8s" beats "reduced 75%")
2. Replacing AI-tell words (leverage, spearhead, orchestrate, etc.) with plain verbs
3. Splitting compound bullets (>15 words or two ideas joined by "and"/"while")
4. Adding specificity: named technologies, team sizes, user counts, constraints
5. Fixing seniority mismatch (entry-level using "led cross-functional strategy")

NEVER suggest changes that fabricate metrics or merge experience scopes.

For each suggestion, provide:
- The exact text to change (original_text)
- Your improved version (proposed_text) — must be under 15 words for bullets
- Why this is better (rationale)
- Where in the resume (location): "summary", "experience.0", "skills", etc.

OUTPUT FORMAT (JSON array):
[
  {
    "location": "summary",
    "original_text": "the exact text from the resume",
    "proposed_text": "your improved version",
    "rationale": "why this is better"
  }
]

Only output the JSON array, no other text."""


# Action verb list for validation
# Excludes AI-tell verbs (spearheaded, orchestrated, streamlined, leveraged, etc.)
# to stay consistent with the POLISHED principle in the prompt.
ACTION_VERBS = {
    "achieved", "accomplished", "accelerated", "administered", "analyzed",
    "automated", "built", "co-led", "collaborated", "configured", "consolidated",
    "created", "cut", "debugged", "delivered", "deployed", "designed", "developed",
    "directed", "eliminated", "enhanced", "established", "executed", "expanded",
    "fixed", "generated", "grew", "guided", "handled", "implemented", "improved",
    "increased", "initiated", "integrated", "introduced", "launched", "led",
    "maintained", "managed", "maximized", "migrated", "minimized", "negotiated",
    "optimized", "organized", "oversaw", "partnered", "piloted", "planned",
    "produced", "promoted", "prototyped", "provided", "rebuilt", "reduced",
    "redesigned", "refactored", "resolved", "restructured", "revamped",
    "saved", "scaled", "secured", "shipped", "simplified", "strengthened",
    "supervised", "taught", "tested", "trained", "transformed", "upgraded",
    "wrote",
}


async def draft_resume_node(state: ResumeState) -> dict[str, Any]:
    """Draft an ATS-friendly resume based on all gathered information.

    Uses raw text directly for better LLM context:
    - Raw profile/resume text (preferred)
    - Raw job posting text (preferred)
    - Gap analysis recommendations
    - Q&A interview responses
    - Discovered experiences from discovery stage
    """
    logger.info("Starting resume drafting node")

    # Prefer raw text fields, fall back to structured data
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_text = state.get("job_text") or state.get("job_markdown") or ""

    # Get metadata for display/filenames
    profile_name = state.get("profile_name") or state.get("user_profile", {}).get("name", "Candidate")
    job_title = state.get("job_title") or state.get("job_posting", {}).get("title", "Position")
    job_company = state.get("job_company") or state.get("job_posting", {}).get("company_name", "Company")

    # Fall back to structured data for contact info if needed
    user_profile = state.get("user_profile", {})
    job_posting = state.get("job_posting", {})
    gap_analysis = state.get("gap_analysis", {})
    qa_history = state.get("qa_history", [])
    research = state.get("research", {})
    discovered_experiences = state.get("discovered_experiences", [])
    user_preferences = state.get("user_preferences", {})

    # Check we have either raw text or structured data
    has_profile = profile_text or user_profile
    has_job = job_text or job_posting

    if not has_profile or not has_job:
        return {
            "errors": [*state.get("errors", []), "Missing profile or job data for drafting"],
            "current_step": "error",
        }

    try:
        llm = get_llm()

        # Build comprehensive drafting context using raw text
        context = _build_drafting_context_from_raw(
            profile_text=profile_text,
            job_text=job_text,
            profile_name=profile_name,
            job_title=job_title,
            job_company=job_company,
            user_profile=user_profile,
            job_posting=job_posting,
            gap_analysis=gap_analysis,
            qa_history=qa_history,
            research=research,
            discovered_experiences=discovered_experiences,
            user_preferences=user_preferences,
        )

        messages = [
            SystemMessage(content=RESUME_DRAFTING_PROMPT),
            HumanMessage(content=f"Create an ATS-optimized resume based on:\n\n{context}"),
        ]

        response = await llm.ainvoke(messages)

        resume_html = _extract_content_from_code_block(response.content, "html")

        logger.info(f"Resume draft generated: {len(resume_html)} characters")

        # Validate and sanitize LLM output for safety
        resume_html, validation_results = validate_output(
            resume_html,
            source_profile=profile_text,
            thread_id=state.get("thread_id"),
        )
        if validation_results["sanitized"]:
            logger.warning("Resume HTML was sanitized to remove problematic patterns")

        # Run programmatic quality checks (bullet length, AI-tells, scope conflation, etc.)
        quality_result = validate_resume(resume_html, source_text=profile_text, job_text=job_text)
        validation_results["quality_checks"] = quality_result.checks
        validation_results["warnings"].extend(quality_result.warnings)
        if quality_result.errors:
            validation_results["warnings"].extend(quality_result.errors)

        # Create initial version
        initial_version = DraftVersion(
            version="1.0",
            html_content=resume_html,
            trigger="initial",
            description="Initial draft generated from profile and job analysis",
            change_log=[],
            created_at=datetime.now().isoformat(),
        )

        # Generate improvement suggestions
        suggestions = await _generate_suggestions(resume_html, job_posting, gap_analysis)

        # Also create structured data for potential JSON editing
        resume_structured = {
            "name": profile_name,
            "contact": {
                "email": user_profile.get("email", ""),
                "phone": user_profile.get("phone", ""),
                "location": user_profile.get("location", ""),
                "linkedin": user_profile.get("linkedin_url", ""),
            },
            "target_job": {
                "title": job_title,
                "company": job_company,
            },
            "keywords_used": gap_analysis.get("keywords_to_include", []),
        }

        return {
            "resume_html": resume_html,
            "resume_draft": resume_structured,
            "draft_suggestions": [s.model_dump() for s in suggestions],
            "draft_versions": [initial_version.model_dump()],
            "draft_change_log": [],
            "draft_current_version": "1.0",
            "draft_approved": False,
            "draft_validation": validation_results,  # Include bias/safety warnings
            "current_step": "editor",  # Set to editor so frontend shows ResumeEditor
            "sub_step": "suggestions_ready",
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Resume drafting error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Resume drafting error: {str(e)}"],
            "current_step": "error",
        }


def _build_drafting_context_from_raw(
    profile_text: str,
    job_text: str,
    profile_name: str,
    job_title: str,
    job_company: str,
    user_profile: dict,
    job_posting: dict,
    gap_analysis: dict,
    qa_history: list,
    research: dict,
    discovered_experiences: list,
    user_preferences: dict | None = None,
) -> str:
    """Build comprehensive context for resume drafting using raw text.

    Uses raw text directly for better LLM understanding, falling back to
    structured data only for contact info.
    """
    # Format user preferences section
    prefs_section = _format_user_preferences(user_preferences)

    # Get contact info from structured data (regex-extracted or user_profile)
    email = user_profile.get('email', '')
    phone = user_profile.get('phone', '')
    location = user_profile.get('location', '')
    linkedin = user_profile.get('linkedin_url', '')

    # Use raw text for profile and job - LLMs work better with natural text
    profile_section = profile_text[:6000] if profile_text else _format_experience_for_draft(user_profile.get('experience', []))
    job_section = job_text[:4000] if job_text else job_posting.get('description', '')[:2000]

    context = f"""
CANDIDATE INFORMATION:
Name: {profile_name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin}

---

CANDIDATE'S FULL RESUME/PROFILE (use this as the primary source):
{profile_section}

---

TARGET JOB:
Title: {job_title}
Company: {job_company}

FULL JOB POSTING (use this as the primary source):
{job_section}

---

TOP REQUIREMENTS TO ADDRESS (include specific evidence for each):
{_format_top_requirements(job_posting, gap_analysis)}

---

GAP ANALYSIS RECOMMENDATIONS:

Strengths to Emphasize:
{chr(10).join('- ' + s for s in gap_analysis.get('strengths', []))}

Areas to Address:
{chr(10).join('- ' + g for g in gap_analysis.get('gaps', []))}

What to Highlight:
{chr(10).join('- ' + e for e in gap_analysis.get('recommended_emphasis', []))}

Keywords to Include: {', '.join(gap_analysis.get('keywords_to_include', []))}

Transferable Skills (reposition these for the target role):
{chr(10).join('- ' + s for s in gap_analysis.get('transferable_skills', []))}

Potential Concerns (address proactively in framing):
{chr(10).join('- ' + c if isinstance(c, str) else '- ' + (c.get('concern', '') + (' — ' + c.get('mitigation', '') if c.get('mitigation') else '')) for c in gap_analysis.get('potential_concerns', []))}

---

ADDITIONAL INFORMATION FROM INTERVIEW:
{_format_qa_for_draft(qa_history)}

---

DISCOVERED EXPERIENCES (from discovery conversation):
{_format_discovered_experiences(discovered_experiences)}

---

COMPANY INSIGHTS:
Culture: {research.get('company_culture', 'N/A')[:500] if research else 'N/A'}
Values: {', '.join(research.get('company_values', [])) if research else 'N/A'}

---

{prefs_section}
"""
    return context


async def _generate_suggestions(
    resume_html: str,
    job_posting: dict,
    gap_analysis: dict,
) -> list[DraftingSuggestion]:
    """Generate improvement suggestions for the resume draft."""
    try:
        llm = get_llm(temperature=0.3)

        prompt = f"""
RESUME DRAFT:
{resume_html}

---

TARGET JOB:
Title: {job_posting.get('title', '')}
Company: {job_posting.get('company_name', '')}

Key Requirements:
{chr(10).join('- ' + r for r in job_posting.get('requirements', [])[:10])}

Keywords that should be included:
{', '.join(gap_analysis.get('keywords_to_include', [])[:15])}

Generate 3-5 specific, actionable suggestions to improve this resume for the target job.
"""

        messages = [
            SystemMessage(content=SUGGESTION_GENERATION_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        content = _extract_content_from_code_block(response.content.strip(), "json")
        suggestions_data = json.loads(content)

        suggestions = []
        for idx, s in enumerate(suggestions_data[:5]):  # Max 5 suggestions
            suggestion = DraftingSuggestion(
                id=f"sug_{uuid.uuid4().hex[:8]}",
                location=s.get("location", "general"),
                original_text=s.get("original_text", ""),
                proposed_text=s.get("proposed_text", ""),
                rationale=s.get("rationale", ""),
                status="pending",
                created_at=datetime.now().isoformat(),
            )
            suggestions.append(suggestion)

        logger.info(f"Generated {len(suggestions)} suggestions")
        return suggestions

    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []


# AI-tell words and phrases that signal AI-generated content
# Source: Research on hiring manager detection patterns
AI_TELL_WORDS = {
    "delve", "leverage", "leveraged", "leveraging", "pivotal", "seamless",
    "seamlessly", "holistic", "synergy", "synergies", "robust", "streamline",
    "streamlined", "streamlining", "spearheaded", "orchestrated",
    "revolutionized", "utilize", "utilized", "utilizing", "innovative",
    "cutting-edge", "dynamic", "passionate",
}

AI_TELL_PHRASES = [
    "proven track record", "results-driven", "results driven",
    "dynamic team player", "exceptional communication",
    "passionate about", "driving innovation", "cross-functional collaboration",
    "demonstrated adaptability", "diverse range", "various tools",
    "multiple technologies", "different projects",
]

GENERIC_FILLER_WORDS = {
    "various", "multiple", "diverse", "exceptional", "outstanding",
    "remarkable", "comprehensive",
}


def detect_ai_tells(text: str) -> list[str]:
    """Detect AI-tell words and phrases in resume text.

    Returns list of found AI-tell words/phrases. Empty list = clean.
    """
    found = []
    lower_text = text.lower()

    for word in AI_TELL_WORDS:
        if re.search(rf'\b{re.escape(word)}\b', lower_text):
            found.append(word)

    for phrase in AI_TELL_PHRASES:
        if phrase in lower_text:
            found.append(phrase)

    return found


def _count_em_dashes(text: str) -> int:
    """Count em dashes (—) and en dashes (–) in text.

    Excessive use is the #1 typographic AI-generation signal.
    """
    return text.count("\u2014") + text.count("\u2013")


def _detect_repetitive_bullet_openings(bullets: list[str]) -> list[str]:
    """Find verbs that start 3+ bullets. Repetitive openings signal AI generation.

    Returns list of words that appear as the first word of 3+ bullets.
    """
    from collections import Counter
    first_words: list[str] = []
    for bullet in bullets:
        clean = re.sub(r'<[^>]+>', '', bullet).strip()
        words = clean.split()
        if words:
            first_words.append(words[0].lower())
    counts = Counter(first_words)
    return [word for word, count in counts.items() if count >= 3]


def _count_bullets_per_role(html_content: str) -> list[tuple[str, int]]:
    """Extract role titles and their bullet counts.

    Returns list of (role_title, bullet_count) tuples.
    Research says 3-5 bullets per role is optimal.
    """
    role_sections = re.split(r'<h3[^>]*>', html_content)
    results = []
    for section in role_sections[1:]:  # Skip content before first h3
        title_match = re.match(r'(.*?)</h3>', section, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else "Unknown"
        bullets = re.findall(r'<li[^>]*>.*?</li>', section, re.DOTALL)
        results.append((title, len(bullets)))
    return results


def _has_quantified_metric(text: str) -> bool:
    """Check if a bullet contains a quantifiable metric.

    Looks for numbers, percentages, dollar amounts, multipliers, and time units.
    Research says 80%+ of bullets should include quantified results.
    """
    metric_patterns = [
        r'\d+%',                      # percentages: 40%, 3.5%
        r'\$[\d,.]+[KMBkmb]?',        # dollar amounts: $1.2M, $500K
        r'\d+[xX]\b',                 # multipliers: 3x, 10X
        r'\b\d+[KMBkmb]\b',          # shorthand numbers: 10K, 1.2M
        r'\b\d+\+?\s*(?:users?|customers?|engineers?|people|team members?|employees?|clients?|requests?|transactions?)',  # counts with units
        r'\b\d+\s*(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?)',  # time units
        r'\bfrom\s+\S+\s+to\s+\S+',  # before/after: "from 3.2s to 0.8s"
        r'\b\d{2,}\b',               # any number >= 10 (filters out single digits in words)
    ]
    for pattern in metric_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _has_rhythm_variation(word_counts: list[int]) -> bool:
    """Check if bullet word counts have enough variation to sound human.

    AI-generated resumes often have uniform sentence structure where 3+
    consecutive bullets have the same word count. Research says hiring managers
    spot this "too polished" cadence in under 20 seconds.

    Returns True if rhythm is varied enough. False means too uniform.
    """
    if len(word_counts) < 3:
        return True  # Too few bullets to judge

    # Check for 3+ consecutive bullets with same word count (±1 word tolerance)
    for i in range(len(word_counts) - 2):
        window = word_counts[i:i + 3]
        avg = sum(window) / len(window)
        if all(abs(wc - avg) <= 1 for wc in window):
            return False

    return True


def _detect_summary_years_claim(summary_text: str) -> list[tuple[int, str]]:
    """Extract 'N+ years [domain]' claims from summary text.

    Returns list of (years, domain) tuples found in the summary.
    Used to cross-check against source material for scope conflation.
    """
    claims = []
    patterns = [
        # "8+ years building AI-powered products"
        r'(\d+)\+?\s+years?\s+(?:of\s+)?(?:experience\s+(?:in|with)\s+)?(.+?)(?:\.|,|and\s|$)',
        # "8 years of AI experience"
        r'(\d+)\+?\s+years?\s+(?:of\s+)?(.+?)\s+experience',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, summary_text, re.IGNORECASE):
            years = int(match.group(1))
            domain = match.group(2).strip().rstrip('.')
            if years >= 3 and len(domain) > 2:
                claims.append((years, domain))
    return claims


def _check_years_domain_grounded(
    years: int, domain: str, source_text: str
) -> bool:
    """Check if a 'N years [domain]' claim is supported by the source text.

    Returns True if the claim appears grounded, False if likely conflated.

    Heuristic: extract key domain words and check if they appear frequently
    enough in the source to justify the year count. If the domain keyword
    appears only once but the years claim spans the whole career,
    it's likely conflation.
    """
    if not source_text or not domain:
        return True  # Can't verify without source

    source_lower = source_text.lower()
    domain_lower = domain.lower()

    # Common abbreviation expansions for tech domains
    abbreviations = {
        "ai": ["artificial intelligence", "ai"],
        "ml": ["machine learning", "ml"],
        "nlp": ["natural language processing", "nlp"],
        "dl": ["deep learning", "dl"],
        "devops": ["devops", "dev ops"],
        "sre": ["site reliability", "sre"],
    }

    # Extract key domain words (skip common filler)
    filler = {"and", "the", "a", "an", "in", "of", "for", "with", "at", "to",
              "on", "by", "is", "are", "was", "were", "be", "been", "being",
              "have", "has", "had", "do", "does", "did", "will", "would",
              "could", "should", "may", "might", "shall", "can", "that",
              "this", "these", "those", "their", "our", "my", "your",
              "its", "all", "each", "every", "both", "few", "more", "most",
              "other", "some", "such", "no", "not", "only", "own", "same",
              "so", "than", "too", "very", "just", "also", "building",
              "built", "creating", "developing", "working", "doing"}
    domain_words = [w for w in domain_lower.split() if w not in filler and len(w) > 2]

    if not domain_words:
        return True

    # Check generic domains that are always fine (broad career descriptions)
    generic_domains = {
        "software", "engineering", "development", "programming",
        "software engineering", "software development", "web development",
        "full-stack", "fullstack", "backend", "frontend", "full stack",
    }
    if domain_lower in generic_domains or all(w in generic_domains for w in domain_words):
        return True

    # Check abbreviation expansions at the domain level
    # e.g., domain "machine learning" should also count "ML" in source
    alias_words = set()
    for abbrev, expansions in abbreviations.items():
        for expansion in expansions:
            if expansion in domain_lower or domain_lower in expansion:
                # Add all variants as aliases to search for
                alias_words.add(abbrev)
                for exp in expansions:
                    for w in exp.split():
                        if w not in filler and len(w) > 2:
                            alias_words.add(w)

    # Count occurrences of domain keywords + aliases in source
    all_search_words = set(domain_words) | alias_words
    domain_mentions = 0
    for word in all_search_words:
        domain_mentions += len(re.findall(rf'\b{re.escape(word)}\b', source_lower))

    # If domain keywords appear < 2 times but years claim is 5+, flag it
    # This catches "8+ years AI" when AI only appears once in the source
    if years >= 5 and domain_mentions < 2:
        return False

    return True


def _detect_ungrounded_scale(resume_text: str, source_text: str) -> list[str]:
    """Detect scale claims in the resume that don't appear in source material.

    Catches cases where employer's scale is attributed to the candidate,
    e.g., 'serving millions of users' when the source never says the
    candidate's work served millions.

    Returns list of flagged scale claims.
    """
    if not source_text:
        return []

    source_lower = source_text.lower()
    resume_lower = resume_text.lower()
    flagged = []

    scale_patterns = [
        (r'serving\s+(?:\d+\s*)?(?:millions?|thousands?|billions?)\s+(?:of\s+)?(?:users?|customers?|clients?)', "serving [scale] users"),
        (r'(?:impacting|reaching|supporting)\s+(?:\d+\s*)?(?:millions?|thousands?|billions?)\s+(?:of\s+)?(?:users?|customers?|clients?)', "impacting [scale] users"),
        (r'(?:serving|reaching|impacting)\s+\d+[MBmb]\+?\s+(?:users?|customers?|clients?)', "serving N+ users"),
        (r'at\s+(?:enterprise\s+)?scale', "at scale"),
        (r'(?:to|for)\s+(?:millions?|thousands?|billions?)\s+(?:of\s+)?(?:users?|people|customers?)', "to millions of users"),
    ]

    for pattern, label in scale_patterns:
        matches = re.findall(pattern, resume_lower)
        if matches:
            # Check if this scale language appears in the source too
            source_matches = re.findall(pattern, source_lower)
            if not source_matches:
                flagged.append(label)

    return flagged


def _is_compound_bullet(text: str) -> bool:
    """Detect compound bullets that join two achievements.

    Only flags when bullet is >12 words AND contains a conjunction joining
    two verb phrases. Short bullets like "Built and deployed API" are fine.
    """
    words = text.split()
    if len(words) <= 12:
        return False

    # Check for conjunction patterns joining two verb phrases
    compound_patterns = [
        r'\b\w+ed\b.*\band\b.*\b\w+(?:ed|ing)\b',  # "Reduced X and improved Y"
        r'\b\w+ed\b.*\bwhile\b.*\b\w+ing\b',         # "Built X while managing Y"
        r'\b\w+ed\b.*\bresulting in\b',                # "Implemented X resulting in Y"
        r'\b\w+ed\b.*\b,\s*\w+ing\b',                 # "Led X, reducing Y"
    ]
    for pattern in compound_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _extract_experience_years(html_content: str) -> list[tuple[str, int | None]]:
    """Extract experience entries and their most recent year from resume HTML.

    Returns a list of (role_text, year) tuples where year is the start/most-recent
    year of that role, or None if no year found. Used to verify reverse chronological order.
    """
    entries = re.findall(r'<h3[^>]*>(.*?)</h3>', html_content, re.IGNORECASE | re.DOTALL)
    results = []
    for entry in entries:
        clean = re.sub(r'<[^>]+>', '', entry).strip()
        # Look for years: "2020-Present", "2020-2023", "Jan 2020 - Present", etc.
        # We want the START year of each role for chronological ordering
        year_matches = re.findall(r'\b(20\d{2})\b', clean)
        if year_matches:
            # The most recent year in the entry is typically the start year or end year
            # For ordering, we use the max year (end date or "Present" implies current)
            if "present" in clean.lower() or "current" in clean.lower():
                results.append((clean, 9999))  # Current role sorts first
            else:
                results.append((clean, max(int(y) for y in year_matches)))
        else:
            results.append((clean, None))
    return results


def _extract_job_keywords(job_text: str) -> list[str]:
    """Extract key terms from a job posting for keyword coverage checking.

    Extracts technology names, tools, skills, and key phrases that a
    tailored resume should mention. Filters out generic words.

    Returns a deduplicated list of lowercase keywords/phrases.
    """
    if not job_text:
        return []

    # Common filler words to skip
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "our", "we",
        "you", "your", "they", "their", "this", "that", "it", "its", "as",
        "if", "not", "no", "so", "up", "out", "about", "into", "over",
        "after", "before", "between", "under", "above", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such",
        "than", "too", "very", "just", "also", "how", "what", "when",
        "where", "who", "which", "while", "during", "through", "across",
        "ability", "experience", "strong", "excellent", "work", "working",
        "team", "role", "position", "company", "including", "etc", "e.g",
        "i.e", "plus", "well", "new", "year", "years", "minimum", "preferred",
        "required", "requirements", "responsibilities", "qualifications",
        "ideal", "candidate", "looking", "join", "opportunity",
    }

    text_lower = job_text.lower()
    keywords = set()

    # 1. Extract technology/tool names (capitalized words, acronyms, versioned names)
    # Match patterns like "React", "AWS", "Python 3", "Node.js", "CI/CD"
    tech_patterns = [
        r'\b[A-Z][a-z]+(?:\.[a-z]+)?\b',           # React, Node.js
        r'\b[A-Z]{2,}\b',                            # AWS, GCP, CI/CD
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',     # Machine Learning, Google Cloud
    ]
    for pattern in tech_patterns:
        for match in re.finditer(pattern, job_text):
            term = match.group().strip()
            if term.lower() not in stop_words and len(term) > 1:
                keywords.add(term.lower())

    # 2. Extract quoted terms (often important requirements)
    for match in re.finditer(r'"([^"]{2,30})"', job_text):
        keywords.add(match.group(1).lower())

    # 3. Extract terms after "experience with/in", "proficiency in", "knowledge of"
    skill_patterns = [
        r'(?:experience\s+(?:with|in)|proficiency\s+in|knowledge\s+of|familiarity\s+with|expertise\s+in)\s+([A-Za-z0-9/\s,]+?)(?:\.|,\s*(?:and|or)|$)',
    ]
    for pattern in skill_patterns:
        for match in re.finditer(pattern, text_lower):
            terms = match.group(1).split(",")
            for term in terms:
                term = term.strip().strip("and ").strip("or ").strip()
                if term and term not in stop_words and len(term) > 2:
                    keywords.add(term)

    # 4. Extract common tech terms that appear as plain words
    common_tech = {
        "python", "javascript", "typescript", "java", "go", "rust", "ruby",
        "c++", "c#", "swift", "kotlin", "scala", "php", "sql", "nosql",
        "react", "angular", "vue", "next.js", "node.js", "express",
        "django", "flask", "fastapi", "spring", "rails",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "graphql", "rest", "grpc", "kafka", "rabbitmq",
        "ci/cd", "devops", "mlops", "agile", "scrum",
        "machine learning", "deep learning", "nlp", "computer vision",
        "microservices", "distributed systems", "data pipeline",
    }
    for tech in common_tech:
        if tech in text_lower:
            keywords.add(tech)

    # Filter out very short or generic results
    return [k for k in keywords if len(k) > 1]


def validate_resume(html_content: str, source_text: str = "", job_text: str = "") -> DraftValidationResult:
    """Validate resume draft against quality criteria.

    Checks:
    - Summary exists and <= 50 words
    - At least 1 experience entry
    - Bullets start with action verbs
    - Bullet word count <= 15 words
    - No compound bullets (two achievements joined)
    - Quantification rate >= 50% (research target: 80%+)
    - AI-tell words/phrases absent
    - Rhythm variation (no 3+ uniform-length consecutive bullets)
    - Summary years+domain grounded in source (scope conflation detection)
    - No ungrounded scale claims (company-to-individual attribution)
    - Keyword coverage >= 30% of job posting key terms (job relevance)
    - Reverse chronological order (newest experience first)
    - Skills section exists
    - Education section exists
    """
    errors = []
    warnings = []
    checks = {}

    # Check summary exists
    summary_match = re.search(
        r'<h2[^>]*>.*?(?:Professional\s+)?Summary.*?</h2>\s*<p[^>]*>(.*?)</p>',
        html_content,
        re.IGNORECASE | re.DOTALL
    )
    checks["summary_exists"] = bool(summary_match)

    if summary_match:
        summary_text = re.sub(r'<[^>]+>', '', summary_match.group(1)).strip()
        word_count = len(summary_text.split())
        checks["summary_length"] = word_count <= 50
        if word_count > 50:
            errors.append(f"Summary is {word_count} words, should be <= 50")
    else:
        errors.append("Professional summary is missing")
        checks["summary_length"] = False

    # Check experience entries
    experience_matches = re.findall(
        r'<h3[^>]*>(.*?)</h3>',
        html_content,
        re.IGNORECASE | re.DOTALL
    )
    checks["experience_count"] = len(experience_matches) >= 1
    if len(experience_matches) < 1:
        errors.append("At least 1 experience entry is required")

    # Check bullets
    bullet_matches = re.findall(r'<li[^>]*>(.*?)</li>', html_content, re.DOTALL)
    action_verb_bullets = 0
    quantified_bullets = 0
    long_bullets = []
    compound_bullets = []
    bullet_word_counts = []

    for bullet in bullet_matches:
        clean_bullet = re.sub(r'<[^>]+>', '', bullet).strip()
        words = clean_bullet.split()
        bullet_word_counts.append(len(words))

        # Action verb check
        first_word = words[0].lower() if words else ""
        if first_word in ACTION_VERBS:
            action_verb_bullets += 1

        # Quantification check (XYZ formula compliance)
        if _has_quantified_metric(clean_bullet):
            quantified_bullets += 1

        # Bullet word count check (skip certification-style bullets)
        if len(words) > 15:
            long_bullets.append(clean_bullet)

        # Compound bullet check
        if _is_compound_bullet(clean_bullet):
            compound_bullets.append(clean_bullet)

    total_bullets = len(bullet_matches)
    if total_bullets > 0:
        action_verb_ratio = action_verb_bullets / total_bullets
        checks["action_verbs"] = action_verb_ratio >= 0.5
        if action_verb_ratio < 0.5:
            warnings.append(f"Only {action_verb_bullets}/{total_bullets} bullets start with action verbs")
    else:
        checks["action_verbs"] = False
        warnings.append("No bullet points found in resume")

    # Bullet word count validation
    checks["bullet_word_count"] = len(long_bullets) == 0
    if long_bullets:
        errors.append(f"{len(long_bullets)} bullet(s) exceed 15 words")
        for b in long_bullets[:3]:
            warnings.append(f"Long bullet ({len(b.split())}w): {b[:80]}...")

    # Compound bullet validation
    checks["no_compound_bullets"] = len(compound_bullets) == 0
    if compound_bullets:
        warnings.append(f"{len(compound_bullets)} bullet(s) contain compound achievements — split into separate bullets")

    # Quantification rate — research says 80%+ bullets should have metrics
    if total_bullets > 0:
        quant_rate = quantified_bullets / total_bullets
        checks["quantification_rate"] = quant_rate >= 0.5
        if quant_rate < 0.5:
            warnings.append(f"Only {quantified_bullets}/{total_bullets} bullets ({quant_rate:.0%}) have quantified metrics — target 80%+")
    else:
        checks["quantification_rate"] = False

    # AI-tell detection — flag AI-sounding words/phrases
    full_text = re.sub(r'<[^>]+>', '', html_content)
    ai_tells_found = detect_ai_tells(full_text)
    checks["ai_tells_clean"] = len(ai_tells_found) == 0
    if ai_tells_found:
        warnings.append(f"AI-tell words/phrases detected ({len(ai_tells_found)}): {', '.join(ai_tells_found[:5])}")

    # Rhythm variation — uniform bullet lengths signal AI generation
    checks["rhythm_variation"] = _has_rhythm_variation(bullet_word_counts)
    if not checks["rhythm_variation"]:
        warnings.append("3+ consecutive bullets have nearly identical word counts — vary rhythm to sound more human")

    # Source-aware checks (only run when source_text is provided)
    if source_text and summary_match:
        summary_text = re.sub(r'<[^>]+>', '', summary_match.group(1)).strip()

        # Scope conflation detection — "8+ years AI" when source shows 8yr SWE + 1yr AI
        years_claims = _detect_summary_years_claim(summary_text)
        all_grounded = True
        for years, domain in years_claims:
            if not _check_years_domain_grounded(years, domain, source_text):
                all_grounded = False
                warnings.append(
                    f"Summary claims '{years}+ years {domain}' — verify this matches your actual years in that specific domain"
                )
        checks["summary_years_grounded"] = all_grounded

        # Scale attribution detection — employer scale attributed to individual
        scale_claims = _detect_ungrounded_scale(full_text, source_text)
        checks["no_ungrounded_scale"] = len(scale_claims) == 0
        if scale_claims:
            warnings.append(
                f"Scale claims not found in your profile ({', '.join(scale_claims)}) — verify these describe YOUR work, not your employer's scale"
            )
    else:
        # Can't check without source — mark as passing
        checks["summary_years_grounded"] = True
        checks["no_ungrounded_scale"] = True

    # Keyword coverage — check if resume addresses key job requirements
    if job_text:
        job_keywords = _extract_job_keywords(job_text)
        if job_keywords:
            resume_text_lower = full_text.lower()
            matched = [kw for kw in job_keywords if kw in resume_text_lower]
            coverage = len(matched) / len(job_keywords)
            checks["keyword_coverage"] = coverage >= 0.3
            if coverage < 0.3:
                missing = [kw for kw in job_keywords if kw not in resume_text_lower]
                warnings.append(
                    f"Low keyword coverage ({coverage:.0%}) — missing job terms: {', '.join(missing[:5])}"
                )
        else:
            checks["keyword_coverage"] = True
    else:
        checks["keyword_coverage"] = True

    # Reverse chronological order — ATS parsers and recruiters expect newest-first
    exp_entries = _extract_experience_years(html_content)
    dated_entries = [(role, yr) for role, yr in exp_entries if yr is not None]
    if len(dated_entries) >= 2:
        years = [yr for _, yr in dated_entries]
        is_reverse_chrono = all(years[i] >= years[i + 1] for i in range(len(years) - 1))
        checks["reverse_chronological"] = is_reverse_chrono
        if not is_reverse_chrono:
            warnings.append("Experience section is not in reverse chronological order — most recent role should come first")
    else:
        checks["reverse_chronological"] = True  # Can't verify with <2 dated entries

    # Check skills section
    skills_match = re.search(
        r'<h2[^>]*>.*?Skills.*?</h2>',
        html_content,
        re.IGNORECASE
    )
    checks["skills_section"] = bool(skills_match)
    if not skills_match:
        errors.append("Skills section is missing")

    # Check education section
    education_match = re.search(
        r'<h2[^>]*>.*?Education.*?</h2>',
        html_content,
        re.IGNORECASE
    )
    checks["education_section"] = bool(education_match)
    if not education_match:
        errors.append("Education section is missing")

    # Em dash detection — excessive em/en dashes are a top AI-generation signal
    em_dash_count = _count_em_dashes(full_text)
    checks["no_excessive_em_dashes"] = em_dash_count < 3
    if em_dash_count >= 3:
        warnings.append(f"{em_dash_count} em/en dashes found — excessive dash usage is a top AI-generation signal")

    # Repetitive bullet openings — 3+ bullets starting with same verb signals AI
    repeated_verbs = _detect_repetitive_bullet_openings(bullet_matches)
    checks["varied_bullet_openings"] = len(repeated_verbs) == 0
    if repeated_verbs:
        warnings.append(f"Bullets repeatedly start with: {', '.join(repeated_verbs)} — vary opening verbs to sound human")

    # Bullets per role — research says 3-5 bullets per role is optimal
    role_bullet_counts = _count_bullets_per_role(html_content)
    all_roles_ok = True
    for role_title, count in role_bullet_counts:
        if count < 3 or count > 5:
            all_roles_ok = False
            break
    checks["bullets_per_role"] = all_roles_ok
    if not all_roles_ok:
        for role_title, count in role_bullet_counts:
            if count < 3:
                warnings.append(f"'{role_title}' has only {count} bullet(s) — aim for 3-5 per role")
            elif count > 5:
                warnings.append(f"'{role_title}' has {count} bullets — consolidate to 3-5 per role")

    valid = len(errors) == 0

    return DraftValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )


def _format_experience_for_draft(experience: list[dict]) -> str:
    """Format experience with full detail for drafting."""
    if not experience:
        return "No experience provided"

    formatted = []
    for exp in experience:
        entry = f"""
Position: {exp.get('position', 'Unknown')}
Company: {exp.get('company', 'Unknown')}
Location: {exp.get('location', 'N/A')}
Duration: {exp.get('start_date', '?')} - {exp.get('end_date', 'Present')}
Current Role: {exp.get('is_current', False)}

Description: {exp.get('description', 'N/A')}

Achievements:
{chr(10).join('  - ' + a for a in exp.get('achievements', []))}

Technologies Used: {', '.join(exp.get('technologies', []))}
"""
        formatted.append(entry)

    return "\n---\n".join(formatted)


def _format_top_requirements(job_posting: dict, gap_analysis: dict) -> str:
    """Extract and format the top job requirements for prominent display.

    Combines structured job requirements, tech stack, and gap analysis
    keywords into a prioritized list so the LLM focuses on specific evidence.
    """
    items = []

    # From structured requirements
    for req in job_posting.get("requirements", [])[:5]:
        items.append(req)

    # From tech stack (deduplicated)
    tech = job_posting.get("tech_stack", [])
    if tech:
        items.append(f"Tech stack: {', '.join(tech[:8])}")

    # From gap analysis keywords (if not already covered)
    keywords = gap_analysis.get("keywords_to_include", [])
    if keywords and not tech:
        items.append(f"Key technologies: {', '.join(keywords[:8])}")

    if not items:
        return "See job posting above for requirements."

    numbered = []
    for i, item in enumerate(items, 1):
        numbered.append(f"{i}. {item} — include a bullet with SPECIFIC evidence from the candidate's profile")
    return "\n".join(numbered)


def _format_qa_for_draft(qa_history: list[dict]) -> str:
    """Format Q&A responses for drafting context."""
    if not qa_history:
        return "No additional information gathered from interview."

    relevant_info = []
    for qa in qa_history:
        if qa.get("answer"):
            # Include Q&A pairs that have answers
            relevant_info.append(f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}")

    if not relevant_info:
        return "No additional information gathered from interview."

    return "\n\n".join(relevant_info)


def _format_discovered_experiences(experiences: list[dict]) -> str:
    """Format discovered experiences for drafting context."""
    if not experiences:
        return "No additional experiences discovered."

    formatted = []
    for exp in experiences:
        entry = f"""
Experience: {exp.get('description', '')}
Quote from user: "{exp.get('source_quote', '')}"
Relevant to: {', '.join(exp.get('mapped_requirements', []))}
"""
        formatted.append(entry)

    return "\n---\n".join(formatted)


def _format_user_preferences(preferences: dict | None) -> str:
    """Format user preferences for drafting context."""
    if not preferences:
        return "USER STYLE PREFERENCES: None specified (use defaults)"

    lines = ["USER STYLE PREFERENCES:"]

    tone_map = {
        "formal": "Use professional, structured language",
        "conversational": "Use friendly, approachable language",
        "confident": "Use bold, assertive language",
        "humble": "Use modest, understated language",
    }
    if preferences.get("tone"):
        lines.append(f"- Tone: {tone_map.get(preferences['tone'], preferences['tone'])}")

    structure_map = {
        "bullets": "Use concise bullet points throughout",
        "paragraphs": "Use flowing narrative paragraphs",
        "mixed": "Combine bullets and paragraphs as appropriate",
    }
    if preferences.get("structure"):
        lines.append(f"- Structure: {structure_map.get(preferences['structure'], preferences['structure'])}")

    sentence_map = {
        "concise": "Keep sentences short and punchy",
        "detailed": "Use comprehensive, detailed explanations",
        "mixed": "Vary sentence length by context",
    }
    if preferences.get("sentence_length"):
        lines.append(f"- Sentence style: {sentence_map.get(preferences['sentence_length'], preferences['sentence_length'])}")

    if preferences.get("first_person") is True:
        lines.append("- Voice: Use first-person 'I' statements (e.g., 'I led a team of 5')")
    elif preferences.get("first_person") is False:
        lines.append("- Voice: Use implied first-person without 'I' (e.g., 'Led a team of 5')")

    quant_map = {
        "heavy_metrics": "Emphasize numbers, percentages, and metrics heavily",
        "qualitative": "Focus on descriptive impact rather than numbers",
        "balanced": "Balance metrics with qualitative descriptions",
    }
    if preferences.get("quantification_preference"):
        lines.append(f"- Quantification: {quant_map.get(preferences['quantification_preference'], preferences['quantification_preference'])}")

    if preferences.get("achievement_focus") is True:
        lines.append("- Focus: Emphasize accomplishments and results over daily responsibilities")
    elif preferences.get("achievement_focus") is False:
        lines.append("- Focus: Include both responsibilities and achievements")

    if len(lines) == 1:
        return "USER STYLE PREFERENCES: None specified (use defaults)"

    return "\n".join(lines)


def increment_version(current_version: str) -> str:
    """Increment version number (e.g., 1.0 -> 1.1, 1.9 -> 2.0)."""
    try:
        major, minor = current_version.split(".")
        minor = int(minor) + 1
        if minor >= 10:
            major = int(major) + 1
            minor = 0
        return f"{major}.{minor}"
    except (ValueError, AttributeError):
        return "1.1"


def create_version(
    html_content: str,
    trigger: str,
    description: str,
    current_version: str,
    change_log: list[dict] = None,
) -> DraftVersion:
    """Create a new version snapshot."""
    new_version = increment_version(current_version)

    return DraftVersion(
        version=new_version,
        html_content=html_content,
        trigger=trigger,
        description=description,
        change_log=change_log or [],
        created_at=datetime.now().isoformat(),
    )
