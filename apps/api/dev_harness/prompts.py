"""Prompt variants for A/B testing.

Each prompt has:
- version: Unique identifier
- system_prompt: The system message
- user_template: Template for user message (use {input} for the raw content)

To add a new variant:
1. Add it to the appropriate *_PROMPTS dict
2. Run benchmarks to compare performance
"""

# =============================================================================
# PROFILE EXTRACTION PROMPTS
# =============================================================================

PROFILE_EXTRACTION_PROMPTS = {
    "v1_original": {
        "version": "v1_original",
        "description": "Original verbose prompt",
        "system_prompt": """You are an expert at extracting structured information from LinkedIn profiles.

Given the raw text content from a LinkedIn profile page, extract the following information in JSON format:

{
    "name": "Full name",
    "headline": "Professional headline",
    "summary": "About/summary section",
    "location": "Location",
    "experience": [
        {
            "company": "Company name",
            "position": "Job title",
            "location": "Location if available",
            "start_date": "Start date",
            "end_date": "End date or null if current",
            "is_current": true/false,
            "achievements": ["Achievement 1", "Achievement 2"],
            "technologies": ["Tech 1", "Tech 2"],
            "description": "Role description"
        }
    ],
    "education": [
        {
            "institution": "School name",
            "degree": "Degree type",
            "field_of_study": "Field",
            "start_date": "Start date",
            "end_date": "End date"
        }
    ],
    "skills": ["Skill 1", "Skill 2"],
    "certifications": ["Cert 1", "Cert 2"],
    "languages": ["Language 1"]
}

Extract as much information as available. If something is not present, omit the field or use null.
Be precise and don't make up information that isn't clearly stated in the profile.""",
        "user_template": "Extract profile information from:\n\n{input}"
    },

    "v2_concise": {
        "version": "v2_concise",
        "description": "Shorter prompt focusing on key fields",
        "system_prompt": """Extract LinkedIn profile data as JSON with these fields:
- name, headline, summary, location
- experience: [{company, position, location, start_date, end_date, is_current, achievements[], technologies[], description}]
- education: [{institution, degree, field_of_study, start_date, end_date}]
- skills[], certifications[]

Be precise. Omit missing fields. Return only valid JSON.""",
        "user_template": "Profile text:\n{input}"
    },

    "v3_structured": {
        "version": "v3_structured",
        "description": "Explicit extraction rules",
        "system_prompt": """You are a profile extraction system. Parse the LinkedIn profile text and return JSON.

EXTRACTION RULES:
1. name: Full name from the top
2. headline: Title line (e.g., "Senior Engineer at Company")
3. summary: "About" section content
4. location: Geographic location
5. experience: For EACH role extract:
   - company: Company name
   - position: Job title
   - dates: start_date, end_date (null if "Present"), is_current
   - achievements: Bullet points with metrics/impact
   - technologies: Languages, tools, frameworks mentioned
   - description: First sentence summary
6. education: School, degree, field, dates
7. skills: Listed skills section
8. certifications: Any certifications mentioned

OUTPUT FORMAT: Valid JSON only. No markdown. No explanations.
MISSING DATA: Omit field entirely (don't use null for optional fields).
ACHIEVEMENTS: Extract bullet points that show impact/metrics.""",
        "user_template": "{input}"
    },

    "v4_haiku_optimized": {
        "version": "v4_haiku_optimized",
        "description": "Optimized for Haiku (fast, cheap)",
        "system_prompt": """Extract LinkedIn profile → JSON:
{name, headline, summary, location, experience[], education[], skills[], certifications[]}

experience[]: {company, position, location, start_date, end_date, is_current, achievements[], technologies[], description}
education[]: {institution, degree, field_of_study, start_date, end_date}

Rules: Precise extraction. Omit missing. JSON only.""",
        "user_template": "{input}"
    }
}

# =============================================================================
# JOB EXTRACTION PROMPTS
# =============================================================================

JOB_EXTRACTION_PROMPTS = {
    "v1_original": {
        "version": "v1_original",
        "description": "Original verbose prompt",
        "system_prompt": """You are an expert at extracting structured information from job postings.

Given the raw text content from a job posting page, extract the following information in JSON format:

{
    "title": "Job title",
    "company_name": "Company name",
    "description": "Full job description",
    "location": "Job location",
    "work_type": "remote/hybrid/onsite",
    "job_type": "full-time/part-time/contract",
    "experience_level": "Entry/Mid/Senior/Lead/Executive",
    "requirements": ["Required qualification 1", "Required qualification 2"],
    "preferred_qualifications": ["Nice to have 1", "Nice to have 2"],
    "responsibilities": ["Responsibility 1", "Responsibility 2"],
    "tech_stack": ["Technology 1", "Framework 2"],
    "benefits": ["Benefit 1", "Benefit 2"],
    "salary_range": "Salary range if mentioned",
    "posted_date": "Posted date if available"
}

Extract as much information as available. If something is not present, omit the field or use null.
Be precise and don't make up information that isn't clearly stated in the posting.
For tech_stack, extract all mentioned programming languages, frameworks, tools, and platforms.""",
        "user_template": "Extract job posting information from:\n\n{input}"
    },

    "v2_concise": {
        "version": "v2_concise",
        "description": "Shorter prompt",
        "system_prompt": """Extract job posting as JSON:
- title, company_name, location, description
- work_type (remote/hybrid/onsite), job_type, experience_level
- requirements[], preferred_qualifications[], responsibilities[]
- tech_stack[] (ALL languages, frameworks, tools, cloud services)
- benefits[], salary_range

Precise extraction. Omit missing. JSON only.""",
        "user_template": "Job posting:\n{input}"
    },

    "v3_tech_focused": {
        "version": "v3_tech_focused",
        "description": "Emphasizes tech stack extraction",
        "system_prompt": """Extract job posting JSON with special attention to technical requirements.

REQUIRED FIELDS:
- title, company_name, location, description
- work_type, job_type, experience_level

LISTS TO EXTRACT CAREFULLY:
- requirements: Hard requirements (years exp, degrees, must-haves)
- preferred_qualifications: Nice-to-haves
- responsibilities: What they'll do day-to-day
- tech_stack: COMPREHENSIVE list of ALL technologies:
  * Programming languages (Python, Go, Java, etc.)
  * Frameworks (React, Django, FastAPI, etc.)
  * Databases (PostgreSQL, Redis, MongoDB, etc.)
  * Cloud/infra (AWS, GCP, K8s, Docker, etc.)
  * Tools (Git, Terraform, Datadog, etc.)
- benefits: Compensation, perks, culture
- salary_range: Extract exact range if mentioned

Output valid JSON only.""",
        "user_template": "{input}"
    }
}

# =============================================================================
# GAP ANALYSIS PROMPTS
# =============================================================================

GAP_ANALYSIS_PROMPTS = {
    "v1_original": {
        "version": "v1_original",
        "description": "Original gap analysis prompt",
        "system_prompt": """You are an expert career coach analyzing resume-job fit.

Given a candidate profile and target job, identify:
1. strengths: Where the candidate exceeds or matches requirements
2. gaps: Missing skills, experience, or qualifications
3. recommended_emphasis: What to highlight in the resume
4. transferable_skills: How existing skills map to requirements
5. keywords_to_include: Important terms from the job posting
6. potential_concerns: Issues to address proactively

Return JSON with these 6 arrays. Be specific and actionable.""",
        "user_template": """CANDIDATE PROFILE:
{profile}

TARGET JOB:
{job}

Analyze the fit and return JSON."""
    },

    "v2_structured": {
        "version": "v2_structured",
        "description": "More structured analysis",
        "system_prompt": """Analyze resume-job fit. Return JSON:

{
  "strengths": ["specific strength matching requirement X"],
  "gaps": ["specific missing requirement"],
  "recommended_emphasis": ["what to highlight + why"],
  "transferable_skills": ["existing skill → job requirement mapping"],
  "keywords_to_include": ["ATS keywords from posting"],
  "potential_concerns": ["issues + how to address"]
}

RULES:
- Be SPECIFIC: "5 years Python experience" not "programming skills"
- Reference actual requirements from job posting
- Map candidate experience to job needs
- Include metrics where candidate has them
- Keywords should come FROM the job posting text""",
        "user_template": """Profile:\n{profile}\n\nJob:\n{job}"""
    }
}


def get_prompt(category: str, version: str) -> dict:
    """Get a specific prompt by category and version."""
    prompts = {
        "profile": PROFILE_EXTRACTION_PROMPTS,
        "job": JOB_EXTRACTION_PROMPTS,
        "gap": GAP_ANALYSIS_PROMPTS,
    }
    if category not in prompts:
        raise ValueError(f"Unknown category: {category}. Use: {list(prompts.keys())}")
    if version not in prompts[category]:
        raise ValueError(f"Unknown version: {version}. Use: {list(prompts[category].keys())}")
    return prompts[category][version]


def list_prompts(category: str) -> list[str]:
    """List all prompt versions for a category."""
    prompts = {
        "profile": PROFILE_EXTRACTION_PROMPTS,
        "job": JOB_EXTRACTION_PROMPTS,
        "gap": GAP_ANALYSIS_PROMPTS,
    }
    if category not in prompts:
        raise ValueError(f"Unknown category: {category}")
    return list(prompts[category].keys())
