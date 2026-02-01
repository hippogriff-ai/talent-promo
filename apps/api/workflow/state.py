"""State schemas for the resume optimization workflow."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ============================================================================
# Profile and Job Data Models
# ============================================================================

class WorkExperience(BaseModel):
    """Work experience entry."""
    company: str
    position: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class Education(BaseModel):
    """Education entry."""
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    achievements: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """Parsed user profile from LinkedIn or resume upload."""
    name: str
    headline: Optional[str] = None
    summary: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class JobPostingData(BaseModel):
    """Parsed job posting - compatible with existing JobPosting type."""
    title: str
    company_name: str
    description: str
    location: Optional[str] = None
    work_type: Optional[str] = None  # remote, hybrid, onsite
    job_type: Optional[str] = None  # full-time, part-time, contract
    experience_level: Optional[str] = None
    requirements: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    salary_range: Optional[str] = None
    source_url: str
    posted_date: Optional[str] = None


# ============================================================================
# Research and Analysis Models
# ============================================================================

class SimilarProfile(BaseModel):
    """LinkedIn profile of a similar employee."""
    name: str
    headline: str
    url: str
    current_company: Optional[str] = None
    key_skills: list[str] = Field(default_factory=list)
    experience_highlights: list[str] = Field(default_factory=list)


class ResearchFindings(BaseModel):
    """Output from research phase."""
    company_overview: str
    company_culture: str
    company_values: list[str] = Field(default_factory=list)
    tech_stack_details: list[dict] = Field(default_factory=list)
    similar_profiles: list[SimilarProfile] = Field(default_factory=list)
    company_news: list[str] = Field(default_factory=list)
    industry_trends: list[str] = Field(default_factory=list)
    hiring_patterns: Optional[str] = None


class GapItem(BaseModel):
    """A gap with linked job requirement."""
    description: str
    requirement_id: Optional[str] = None
    """ID of the linked job requirement."""
    requirement_text: Optional[str] = None
    """Text of the linked job requirement."""
    priority: int = 1
    """Priority level (1 = highest)."""


class OpportunityItem(BaseModel):
    """An opportunity angle to explore."""
    description: str
    related_gaps: list[str] = Field(default_factory=list)
    """Gap descriptions this opportunity addresses."""
    potential_impact: str = "medium"
    """high, medium, low"""


class GapAnalysis(BaseModel):
    """Output from gap analysis phase."""
    strengths: list[str] = Field(default_factory=list)
    """Skills/experiences user already has that match the job."""

    gaps: list[str] = Field(default_factory=list)
    """Areas where user may need to develop or highlight differently."""

    gaps_detailed: list[GapItem] = Field(default_factory=list)
    """Detailed gap items with linked job requirements."""

    opportunities: list[OpportunityItem] = Field(default_factory=list)
    """Potential angles to explore in discovery."""

    recommended_emphasis: list[str] = Field(default_factory=list)
    """What to emphasize in the resume."""

    transferable_skills: list[str] = Field(default_factory=list)
    """Skills that can be repositioned for this role."""

    keywords_to_include: list[str] = Field(default_factory=list)
    """ATS keywords that should appear in the resume."""

    potential_concerns: list[str] = Field(default_factory=list)
    """Potential red flags to address proactively."""


# ============================================================================
# Discovery Models
# ============================================================================

class AgendaTopic(BaseModel):
    """A high-level topic in the discovery agenda."""
    id: str
    title: str
    """Short title displayed in UI, e.g., 'Leadership Experience'"""
    goal: str
    """What we want to discover about this topic."""
    related_gaps: list[str] = Field(default_factory=list)
    """Which gaps this topic addresses."""
    priority: int = 1
    """Order in the agenda (1 = highest priority)."""
    status: Literal["pending", "in_progress", "covered", "skipped"] = "pending"
    """Current status of this topic."""
    prompts_asked: int = 0
    """Number of prompts asked for this topic."""
    max_prompts: int = 2
    """Maximum prompts to ask per topic (prevents over-drilling)."""
    experiences_found: list[str] = Field(default_factory=list)
    """IDs of experiences discovered for this topic."""


class DiscoveryAgenda(BaseModel):
    """Structured agenda for the discovery phase."""
    topics: list[AgendaTopic] = Field(default_factory=list)
    """The 5-6 high-level topics to cover."""
    current_topic_id: Optional[str] = None
    """ID of the topic currently being discussed."""
    total_topics: int = 0
    """Total number of topics in the agenda."""
    covered_topics: int = 0
    """Number of topics marked as covered or skipped."""


class DiscoveryPrompt(BaseModel):
    """A discovery prompt to surface hidden experience."""
    id: str
    question: str
    intent: str
    """What the prompt is trying to uncover."""
    related_gaps: list[str] = Field(default_factory=list)
    """Gap descriptions this prompt addresses."""
    priority: int = 1
    """Priority level (1 = highest, ordered by relevance to gaps)."""
    asked: bool = False
    """Whether this prompt has been asked."""
    topic_id: Optional[str] = None
    """ID of the agenda topic this prompt belongs to."""
    is_follow_up: bool = False
    """Whether this is a dynamically generated follow-up question."""


class DiscoveredExperience(BaseModel):
    """An experience discovered during the discovery conversation."""
    id: str
    description: str
    source_quote: str
    """Exact quote from user's response that revealed this experience."""
    mapped_requirements: list[str] = Field(default_factory=list)
    """Job requirements this experience addresses."""
    discovered_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class DiscoveryMessage(BaseModel):
    """A message in the discovery conversation."""
    role: str  # "agent" or "user"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    prompt_id: Optional[str] = None
    """If agent message, the prompt ID it corresponds to."""
    experiences_extracted: list[str] = Field(default_factory=list)
    """IDs of experiences extracted from this message (if user message)."""


# ============================================================================
# Human-in-the-Loop Models
# ============================================================================

class QAInteraction(BaseModel):
    """Single Q&A interaction."""
    question: str
    answer: Optional[str] = None
    question_intent: Optional[str] = None  # What the agent is trying to learn
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# Resume Draft Models
# ============================================================================

class ResumeSectionEdit(BaseModel):
    """Edit suggestion for a resume section."""
    section: str  # e.g., "summary", "experience.0.achievements"
    original: str
    suggested: str
    reason: str


class ResumeContent(BaseModel):
    """Structured resume content."""
    summary: str
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    # HTML version for Tiptap editor
    html_content: Optional[str] = None


# ============================================================================
# Drafting Stage Models
# ============================================================================

SuggestionStatus = Literal["pending", "accepted", "declined"]
VersionTrigger = Literal["initial", "accept", "decline", "edit", "manual_save", "auto_checkpoint", "restore"]


class DraftingSuggestion(BaseModel):
    """A suggestion for improving the resume draft."""
    id: str
    location: str
    """Section or path in resume (e.g., 'summary', 'experience.0.achievements.1')"""
    original_text: str
    proposed_text: str
    rationale: str
    status: SuggestionStatus = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None


class DraftChangeLogEntry(BaseModel):
    """A log entry for a change made to the draft."""
    id: str
    location: str
    """Section that was changed"""
    change_type: str
    """'accept', 'decline', 'edit'"""
    original_text: Optional[str] = None
    new_text: Optional[str] = None
    suggestion_id: Optional[str] = None
    """If change was from accepting/declining a suggestion"""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DraftVersion(BaseModel):
    """A version snapshot of the resume draft."""
    version: str
    """Version number like '1.0', '1.1', '2.0'"""
    html_content: str
    trigger: VersionTrigger
    """What triggered this version save"""
    description: str
    """Human-readable description of what changed"""
    change_log: list[DraftChangeLogEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class DraftValidationResult(BaseModel):
    """Result of resume draft validation."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    """Individual check results: summary_exists, summary_length, experience_count, etc."""


# ============================================================================
# Memory Hierarchy Models (for context management)
# ============================================================================

class WorkingContext(BaseModel):
    """Working memory - current task focus (kept small for LLM context).

    This is what gets passed to LLM calls to avoid context bloat.
    Updated at each step with only relevant information.
    """
    # Current focus
    target_role: str = ""
    target_company: str = ""

    # Key insights (summarized, not full data)
    key_strengths: list[str] = Field(default_factory=list, max_length=5)
    key_gaps: list[str] = Field(default_factory=list, max_length=5)
    priority_keywords: list[str] = Field(default_factory=list, max_length=10)

    # Recent Q&A (only last few for context)
    recent_qa: list[dict] = Field(default_factory=list, max_length=3)

    # Current action
    current_objective: str = ""

    def to_prompt_context(self) -> str:
        """Format working context for LLM prompts."""
        parts = [
            f"Target: {self.target_role} at {self.target_company}",
        ]
        if self.key_strengths:
            parts.append(f"Strengths: {', '.join(self.key_strengths)}")
        if self.key_gaps:
            parts.append(f"Gaps to address: {', '.join(self.key_gaps)}")
        if self.priority_keywords:
            parts.append(f"Keywords: {', '.join(self.priority_keywords)}")
        if self.recent_qa:
            qa_summary = "; ".join([
                f"Q: {qa.get('question', '')[:50]}... A: {qa.get('answer', '')[:50]}..."
                for qa in self.recent_qa[-2:]
            ])
            parts.append(f"Recent Q&A: {qa_summary}")
        return "\n".join(parts)


class InterruptPayload(BaseModel):
    """Payload sent to frontend during interrupt.

    This enables progressive information disclosure - we only send
    what the user needs to see at each interrupt point.
    """
    interrupt_type: str  # "qa_question", "review_draft", "confirm_export"
    message: str

    # Context for the user (what they need to make a decision)
    context: dict = Field(default_factory=dict)

    # Options/suggestions if applicable
    suggestions: list[str] = Field(default_factory=list)

    # Metadata
    round: int = 0
    max_rounds: int = 10
    can_skip: bool = True


# ============================================================================
# Export Stage Models
# ============================================================================


class ATSReport(BaseModel):
    """ATS analysis report for a resume."""
    keyword_match_score: int = 0
    """Score from 0-100 indicating keyword match percentage."""
    matched_keywords: list[str] = Field(default_factory=list)
    """Keywords found in resume that match job requirements."""
    missing_keywords: list[str] = Field(default_factory=list)
    """Keywords from job that are missing in resume."""
    formatting_issues: list[str] = Field(default_factory=list)
    """List of formatting issues that may affect ATS parsing."""
    recommendations: list[str] = Field(default_factory=list)
    """Suggestions to improve ATS compatibility."""
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class LinkedInSuggestion(BaseModel):
    """LinkedIn optimization suggestions."""
    headline: str = ""
    """Suggested LinkedIn headline."""
    summary: str = ""
    """Suggested LinkedIn summary/about section."""
    experience_bullets: list[dict] = Field(default_factory=list)
    """Experience bullets mapped to LinkedIn sections. Each dict has 'company', 'position', 'bullets'."""
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ExportOutput(BaseModel):
    """Export stage output containing all generated artifacts."""
    pdf_generated: bool = False
    txt_generated: bool = False
    json_generated: bool = False
    ats_report: Optional[ATSReport] = None
    linkedin_suggestions: Optional[LinkedInSuggestion] = None
    export_completed: bool = False
    completed_at: Optional[str] = None


ExportStep = Literal[
    "optimizing",
    "generating_pdf",
    "generating_txt",
    "generating_json",
    "analyzing_ats",
    "generating_linkedin",
    "completed"
]


# ============================================================================
# Main Workflow State
# ============================================================================

WorkflowStep = Literal[
    "ingest",
    "research",
    "analysis",
    "discovery",
    "qa",
    "draft",
    "editor",
    "export",
    "completed",
    "error"
]


class ResumeState(TypedDict):
    """Main state for the resume optimization workflow.

    This state persists across all workflow steps and supports
    human-in-the-loop interrupts via LangGraph checkpointing.

    Memory Hierarchy:
    - Full state: Complete data for persistence and recovery
    - Working context: Summarized context for LLM calls (prevents bloat)
    - Interrupt payload: What user sees during human-in-the-loop
    """
    # Inputs
    linkedin_url: Optional[str]
    job_url: Optional[str]
    uploaded_resume_text: Optional[str]
    uploaded_job_text: Optional[str]  # Pasted job description as fallback

    # Raw markdown from EXA (for display and user editing)
    profile_markdown: Optional[str]  # Raw LinkedIn markdown from EXA
    job_markdown: Optional[str]  # Raw job posting markdown from EXA

    # Raw text fields (PRIMARY - used by downstream LLMs)
    # These are preferred over structured data for LLM consumption
    profile_text: Optional[str]  # Raw profile/resume text
    job_text: Optional[str]  # Raw job posting text

    # Extracted metadata (simple regex, no LLM)
    # For filenames, display, and quick lookups
    profile_name: Optional[str]  # Candidate name for filenames
    job_title: Optional[str]  # Job title for display
    job_company: Optional[str]  # Company name for display

    # Parsed data (backward-compatible structured data for UI components)
    # NOTE: These are minimal/empty when using raw_text extraction method
    user_profile: Optional[dict]  # Serialized UserProfile
    job_posting: Optional[dict]   # Serialized JobPostingData

    # Workflow outputs (full - stored for recovery)
    research: Optional[dict]      # Serialized ResearchFindings
    gap_analysis: Optional[dict]  # Serialized GapAnalysis

    # Working context (summarized - for LLM calls)
    working_context: Optional[dict]  # Serialized WorkingContext

    # Discovery stage
    discovery_prompts: list[dict]  # List of serialized DiscoveryPrompt
    discovery_messages: list[dict]  # List of serialized DiscoveryMessage (conversation log)
    discovered_experiences: list[dict]  # List of serialized DiscoveredExperience
    discovery_confirmed: bool  # True when user confirms discovery is complete
    discovery_exchanges: int  # Number of conversation exchanges
    discovery_phase: Optional[str]  # "setup" or "waiting" - controls two-phase interrupt flow
    pending_prompt_id: Optional[str]  # ID of prompt awaiting response
    discovery_agenda: Optional[dict]  # Serialized DiscoveryAgenda - structured topic tracker

    # Human-in-the-loop Q&A
    qa_history: list[dict]  # List of serialized QAInteraction
    qa_round: int
    qa_complete: bool
    user_done_signal: bool  # True when user explicitly says "done"

    # Current interrupt (for frontend progressive disclosure)
    pending_interrupt: Optional[dict]  # Serialized InterruptPayload

    # Resume generation
    resume_draft: Optional[dict]  # Serialized ResumeContent
    resume_html: Optional[str]    # Tiptap-compatible HTML
    resume_final: Optional[str]   # Final HTML after user edits

    # Drafting stage
    draft_suggestions: list[dict]  # List of serialized DraftingSuggestion
    draft_versions: list[dict]  # List of serialized DraftVersion (max 5)
    draft_change_log: list[dict]  # List of serialized DraftChangeLogEntry
    draft_current_version: Optional[str]  # Current version number
    draft_approved: bool  # True when user approves the final draft

    # Export stage
    export_format: Optional[str]  # "docx" or "pdf"
    export_path: Optional[str]
    export_output: Optional[dict]  # Serialized ExportOutput
    export_step: Optional[str]  # Current export sub-step
    ats_report: Optional[dict]  # Serialized ATSReport
    linkedin_suggestions: Optional[dict]  # Serialized LinkedInSuggestion
    export_completed: bool

    # Metadata
    current_step: WorkflowStep
    sub_step: Optional[str]  # Granular progress: "fetching_profile", "profile_fetched", etc.
    errors: list[str]
    messages: list  # For LangGraph MessagesState compatibility

    # Progress tracking (for real-time UI updates)
    progress_messages: list[dict]  # List of {timestamp, phase, message, detail} for live progress

    # User preferences for writing style
    user_preferences: Optional[dict]  # Tone, structure, quantification preferences

    # Timestamps
    created_at: str
    updated_at: str
