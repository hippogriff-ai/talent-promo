"""State models for Workflow Variant B (Deep Agents).

Variant B uses the same ResumeState as Variant A to ensure
outputs are comparable in the Arena A/B comparison.
"""

from workflow.state import (
    ResumeState,
    UserProfile,
    JobPostingData,
    ResearchFindings,
    GapAnalysis,
    WorkingContext,
    InterruptPayload,
    DiscoveryPrompt,
    DiscoveryMessage,
    DiscoveredExperience,
    QAInteraction,
    DraftingSuggestion,
    DraftVersion,
    DraftChangeLogEntry,
    ATSReport,
    LinkedInSuggestion,
    ExportOutput,
)

# Re-export all state models for use in Variant B
__all__ = [
    "ResumeState",
    "UserProfile",
    "JobPostingData",
    "ResearchFindings",
    "GapAnalysis",
    "WorkingContext",
    "InterruptPayload",
    "DiscoveryPrompt",
    "DiscoveryMessage",
    "DiscoveredExperience",
    "QAInteraction",
    "DraftingSuggestion",
    "DraftVersion",
    "DraftChangeLogEntry",
    "ATSReport",
    "LinkedInSuggestion",
    "ExportOutput",
]
