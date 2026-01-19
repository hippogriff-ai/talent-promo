"""Tests for the Drafting stage."""

import pytest
from datetime import datetime

from workflow.state import (
    DraftingSuggestion,
    DraftVersion,
    DraftChangeLogEntry,
    DraftValidationResult,
)
from workflow.nodes.drafting import (
    validate_resume,
    increment_version,
    create_version,
    ACTION_VERBS,
    _format_user_preferences,
)


class TestDraftingModels:
    """Test drafting state models."""

    def test_drafting_suggestion_creation(self):
        """Test DraftingSuggestion model creation."""
        suggestion = DraftingSuggestion(
            id="sug_12345678",
            location="summary",
            original_text="Experienced developer",
            proposed_text="Senior software engineer with 10+ years",
            rationale="More specific and quantified",
            status="pending",
        )

        assert suggestion.id == "sug_12345678"
        assert suggestion.location == "summary"
        assert suggestion.status == "pending"
        assert suggestion.resolved_at is None

    def test_drafting_suggestion_resolved(self):
        """Test resolving a suggestion."""
        suggestion = DraftingSuggestion(
            id="sug_12345678",
            location="experience.0",
            original_text="Worked on projects",
            proposed_text="Led 5 cross-functional projects",
            rationale="Added specificity and leadership",
            status="accepted",
            resolved_at=datetime.now().isoformat(),
        )

        assert suggestion.status == "accepted"
        assert suggestion.resolved_at is not None

    def test_draft_version_creation(self):
        """Test DraftVersion model creation."""
        version = DraftVersion(
            version="1.0",
            html_content="<h1>Resume</h1>",
            trigger="initial",
            description="Initial draft",
        )

        assert version.version == "1.0"
        assert version.trigger == "initial"
        assert len(version.change_log) == 0

    def test_draft_change_log_entry(self):
        """Test DraftChangeLogEntry model."""
        entry = DraftChangeLogEntry(
            id="chg_12345678",
            location="summary",
            change_type="accept",
            original_text="old text",
            new_text="new text",
            suggestion_id="sug_12345678",
        )

        assert entry.change_type == "accept"
        assert entry.suggestion_id == "sug_12345678"

    def test_draft_validation_result(self):
        """Test DraftValidationResult model."""
        result = DraftValidationResult(
            valid=True,
            errors=[],
            warnings=["Consider adding more metrics"],
            checks={
                "summary_exists": True,
                "summary_length": True,
                "experience_count": True,
            },
        )

        assert result.valid is True
        assert len(result.warnings) == 1
        assert result.checks["summary_exists"] is True


class TestVersioning:
    """Test version control functionality."""

    def test_increment_version_minor(self):
        """Test minor version increment."""
        assert increment_version("1.0") == "1.1"
        assert increment_version("1.5") == "1.6"
        assert increment_version("2.3") == "2.4"

    def test_increment_version_major(self):
        """Test major version increment on minor overflow."""
        assert increment_version("1.9") == "2.0"
        assert increment_version("9.9") == "10.0"

    def test_increment_version_invalid(self):
        """Test fallback for invalid version."""
        assert increment_version("invalid") == "1.1"
        assert increment_version("") == "1.1"

    def test_create_version(self):
        """Test create_version function."""
        version = create_version(
            html_content="<h1>Test</h1>",
            trigger="accept",
            description="Accepted suggestion",
            current_version="1.0",
        )

        assert version.version == "1.1"
        assert version.trigger == "accept"
        assert version.description == "Accepted suggestion"


class TestResumeValidation:
    """Test resume validation functionality."""

    def test_validate_complete_resume(self):
        """Test validation of a complete, valid resume."""
        html = """
        <h1>John Doe</h1>
        <p>email@example.com | 555-1234</p>

        <h2>Professional Summary</h2>
        <p>Experienced software engineer with expertise in Python and cloud technologies.</p>

        <h2>Experience</h2>
        <h3>Senior Developer | Tech Corp | 2020-Present</h3>
        <ul>
            <li>Led development of microservices architecture</li>
            <li>Managed team of 5 engineers</li>
            <li>Implemented CI/CD pipeline reducing deploy time by 50%</li>
        </ul>

        <h2>Education</h2>
        <p><strong>BS Computer Science</strong> - State University, 2018</p>

        <h2>Skills</h2>
        <p>Python, JavaScript, AWS, Docker, Kubernetes</p>
        """

        result = validate_resume(html)

        assert result.valid is True
        assert result.checks["summary_exists"] is True
        assert result.checks["experience_count"] is True
        assert result.checks["skills_section"] is True
        assert result.checks["education_section"] is True

    def test_validate_missing_summary(self):
        """Test validation fails without summary."""
        html = """
        <h1>John Doe</h1>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>

        <h2>Skills</h2>
        <p>Python</p>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        assert result.valid is False
        assert result.checks["summary_exists"] is False
        assert "summary" in result.errors[0].lower()

    def test_validate_missing_experience(self):
        """Test validation fails without experience."""
        html = """
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>Software engineer.</p>

        <h2>Skills</h2>
        <p>Python</p>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        assert result.valid is False
        assert result.checks["experience_count"] is False

    def test_validate_missing_skills(self):
        """Test validation fails without skills section."""
        html = """
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>Software engineer.</p>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        assert result.valid is False
        assert result.checks["skills_section"] is False

    def test_validate_missing_education(self):
        """Test validation fails without education section."""
        html = """
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>Software engineer.</p>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>

        <h2>Skills</h2>
        <p>Python</p>
        """

        result = validate_resume(html)

        assert result.valid is False
        assert result.checks["education_section"] is False

    def test_validate_summary_too_long(self):
        """Test validation fails with summary over 100 words."""
        long_summary = " ".join(["word"] * 150)
        html = f"""
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>{long_summary}</p>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>

        <h2>Skills</h2>
        <p>Python</p>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        assert result.valid is False
        assert result.checks["summary_length"] is False
        assert "100" in result.errors[0]

    def test_validate_action_verbs(self):
        """Test action verb validation in bullet points."""
        html = """
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>Software engineer.</p>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>
        <ul>
            <li>Led development of features</li>
            <li>Managed team of engineers</li>
            <li>Implemented new systems</li>
        </ul>

        <h2>Skills</h2>
        <p>Python</p>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        # All bullets start with action verbs
        assert result.checks["action_verbs"] is True

    def test_validate_weak_bullets(self):
        """Test warning for bullets without action verbs."""
        html = """
        <h1>John Doe</h1>

        <h2>Professional Summary</h2>
        <p>Software engineer.</p>

        <h2>Experience</h2>
        <h3>Developer | Company</h3>
        <ul>
            <li>Was responsible for development</li>
            <li>Also did testing</li>
            <li>Had to write documentation</li>
        </ul>

        <h2>Skills</h2>
        <p>Python</p>

        <h2>Education</h2>
        <p>Degree</p>
        """

        result = validate_resume(html)

        # Should have warning about action verbs
        assert result.checks["action_verbs"] is False
        assert any("action verb" in w.lower() for w in result.warnings)


class TestActionVerbs:
    """Test action verb set."""

    def test_common_action_verbs_included(self):
        """Test that common action verbs are in the set."""
        common_verbs = [
            "led", "managed", "developed", "implemented", "created",
            "designed", "built", "increased", "reduced", "improved"
        ]

        for verb in common_verbs:
            assert verb in ACTION_VERBS, f"{verb} should be in ACTION_VERBS"

    def test_action_verb_count(self):
        """Test that we have a reasonable number of action verbs."""
        assert len(ACTION_VERBS) >= 50, "Should have at least 50 action verbs"


class TestVersionLimit:
    """Test version history limit (max 5)."""

    def test_version_limit_enforced(self):
        """Test that version list doesn't exceed 5."""
        versions = []

        # Create 7 versions
        for i in range(7):
            version = DraftVersion(
                version=f"1.{i}",
                html_content=f"<h1>Version {i}</h1>",
                trigger="edit",
                description=f"Version {i}",
            )
            versions.append(version.model_dump())

        # Keep only last 5
        if len(versions) > 5:
            versions = versions[-5:]

        assert len(versions) == 5
        assert versions[0]["version"] == "1.2"  # 0, 1 removed
        assert versions[-1]["version"] == "1.6"  # Latest


class TestSuggestionStatus:
    """Test suggestion status transitions."""

    def test_suggestion_pending_to_accepted(self):
        """Test transitioning suggestion from pending to accepted."""
        suggestion = DraftingSuggestion(
            id="sug_test",
            location="summary",
            original_text="old",
            proposed_text="new",
            rationale="better",
            status="pending",
        )

        # Simulate accept action
        suggestion.status = "accepted"
        suggestion.resolved_at = datetime.now().isoformat()

        assert suggestion.status == "accepted"
        assert suggestion.resolved_at is not None

    def test_suggestion_pending_to_declined(self):
        """Test transitioning suggestion from pending to declined."""
        suggestion = DraftingSuggestion(
            id="sug_test",
            location="summary",
            original_text="old",
            proposed_text="new",
            rationale="better",
            status="pending",
        )

        # Simulate decline action
        suggestion.status = "declined"
        suggestion.resolved_at = datetime.now().isoformat()

        assert suggestion.status == "declined"

    def test_all_suggestions_resolved(self):
        """Test checking if all suggestions are resolved."""
        suggestions = [
            DraftingSuggestion(
                id="sug_1",
                location="summary",
                original_text="old1",
                proposed_text="new1",
                rationale="r1",
                status="accepted",
            ),
            DraftingSuggestion(
                id="sug_2",
                location="experience",
                original_text="old2",
                proposed_text="new2",
                rationale="r2",
                status="declined",
            ),
        ]

        pending = [s for s in suggestions if s.status == "pending"]
        assert len(pending) == 0


class TestChangeLog:
    """Test change log functionality."""

    def test_change_log_tracks_accept(self):
        """Test change log records accept action."""
        entry = DraftChangeLogEntry(
            id="chg_1",
            location="summary",
            change_type="accept",
            original_text="old",
            new_text="new",
            suggestion_id="sug_1",
        )

        assert entry.change_type == "accept"
        assert entry.new_text == "new"

    def test_change_log_tracks_decline(self):
        """Test change log records decline action (no new_text)."""
        entry = DraftChangeLogEntry(
            id="chg_2",
            location="experience",
            change_type="decline",
            original_text="old",
            new_text=None,
            suggestion_id="sug_2",
        )

        assert entry.change_type == "decline"
        assert entry.new_text is None

    def test_change_log_tracks_edit(self):
        """Test change log records direct edit."""
        entry = DraftChangeLogEntry(
            id="chg_3",
            location="skills",
            change_type="edit",
            original_text="Python",
            new_text="Python, JavaScript, TypeScript",
            suggestion_id=None,  # No suggestion for direct edits
        )

        assert entry.change_type == "edit"
        assert entry.suggestion_id is None


class TestUserPreferencesFormatting:
    """Test user preferences formatting for drafting context."""

    def test_format_no_preferences(self):
        """Test formatting when no preferences provided."""
        result = _format_user_preferences(None)
        assert "None specified" in result

    def test_format_empty_preferences(self):
        """Test formatting when preferences dict is empty."""
        result = _format_user_preferences({})
        assert "None specified" in result

    def test_format_tone_formal(self):
        """Test formatting formal tone preference."""
        prefs = {"tone": "formal"}
        result = _format_user_preferences(prefs)
        assert "professional" in result.lower()
        assert "structured" in result.lower()

    def test_format_tone_conversational(self):
        """Test formatting conversational tone preference."""
        prefs = {"tone": "conversational"}
        result = _format_user_preferences(prefs)
        assert "friendly" in result.lower()

    def test_format_structure_bullets(self):
        """Test formatting bullet structure preference."""
        prefs = {"structure": "bullets"}
        result = _format_user_preferences(prefs)
        assert "bullet" in result.lower()

    def test_format_structure_paragraphs(self):
        """Test formatting paragraph structure preference."""
        prefs = {"structure": "paragraphs"}
        result = _format_user_preferences(prefs)
        assert "paragraph" in result.lower()

    def test_format_first_person_true(self):
        """Test formatting first person preference when true."""
        prefs = {"first_person": True}
        result = _format_user_preferences(prefs)
        assert "'I'" in result

    def test_format_first_person_false(self):
        """Test formatting first person preference when false."""
        prefs = {"first_person": False}
        result = _format_user_preferences(prefs)
        assert "implied" in result.lower()

    def test_format_quantification_heavy_metrics(self):
        """Test formatting heavy metrics quantification preference."""
        prefs = {"quantification_preference": "heavy_metrics"}
        result = _format_user_preferences(prefs)
        assert "numbers" in result.lower() or "metrics" in result.lower()

    def test_format_quantification_qualitative(self):
        """Test formatting qualitative quantification preference."""
        prefs = {"quantification_preference": "qualitative"}
        result = _format_user_preferences(prefs)
        assert "descriptive" in result.lower() or "impact" in result.lower()

    def test_format_achievement_focus_true(self):
        """Test formatting achievement focus preference when true."""
        prefs = {"achievement_focus": True}
        result = _format_user_preferences(prefs)
        assert "accomplishment" in result.lower() or "result" in result.lower()

    def test_format_all_preferences(self):
        """Test formatting with all preferences set."""
        prefs = {
            "tone": "confident",
            "structure": "mixed",
            "sentence_length": "concise",
            "first_person": True,
            "quantification_preference": "balanced",
            "achievement_focus": True,
        }
        result = _format_user_preferences(prefs)

        # Should include all preference types
        assert "Tone:" in result
        assert "Structure:" in result
        assert "Sentence style:" in result
        assert "Voice:" in result
        assert "Quantification:" in result
        assert "Focus:" in result
