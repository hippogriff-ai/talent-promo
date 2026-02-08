"""Tests for drafting quality validation (Phase 1 TDD scaffolding).

Category A: Programmatic validation tests (no LLM calls)
- TestBulletWordCount: validate_resume() catches bullets > 15 words
- TestCompoundSentences: validate_resume() catches compound achievements
- TestAITellDetection: detect_ai_tells() finds AI-sounding words/phrases
- TestRhythmVariation: _has_rhythm_variation() detects uniform bullet cadence
- TestScopeConflation: detects "N+ years [domain]" claims not grounded in source
- TestScaleAttribution: detects employer-scale claims attributed to individual
- TestKeywordCoverage: _extract_job_keywords() + keyword_coverage check
- TestReverseChronological: _extract_experience_years() + reverse_chronological check
- TestSummaryLength: validate_resume() catches summaries > 50 words
- TestDatasetIntegrity: all samples have profile_text, traps have dimension expectations

Category B: Grader structure tests (no LLM calls)
- TestGraderDimensions: grader has 6 dimensions with correct weights
- TestGraderSignature: grade() accepts original_resume_text
"""

import json
import pytest
from pathlib import Path

from workflow.nodes.drafting import (
    validate_resume, _is_compound_bullet, _has_quantified_metric,
    _has_rhythm_variation, detect_ai_tells,
    _detect_summary_years_claim, _check_years_domain_grounded,
    _detect_ungrounded_scale, _extract_job_keywords,
    _extract_experience_years,
    _count_em_dashes, _detect_repetitive_bullet_openings,
    _count_bullets_per_role,
)


def _make_resume_html(
    summary: str = "Software engineer with 5 years experience.",
    bullets: list[str] | None = None,
    include_skills: bool = True,
    include_education: bool = True,
) -> str:
    """Build a minimal valid resume HTML for testing."""
    if bullets is None:
        bullets = ["Built backend API serving 10K users"]

    bullet_html = "\n".join(f"<li>{b}</li>" for b in bullets)

    sections = [
        '<h1>Test Candidate</h1>',
        '<p>test@email.com | 555-1234</p>',
        '<h2>Professional Summary</h2>',
        f'<p>{summary}</p>',
        '<h2>Experience</h2>',
        '<h3>Engineer | Company | 2020-Present</h3>',
        f'<ul>{bullet_html}</ul>',
    ]

    if include_skills:
        sections.append('<h2>Skills</h2>')
        sections.append('<p>Python, JavaScript</p>')

    if include_education:
        sections.append('<h2>Education</h2>')
        sections.append('<p><strong>BS CS</strong> - University, 2018</p>')

    return "\n".join(sections)


class TestBulletWordCount:
    """validate_resume() catches bullets > 15 words."""

    def test_short_bullets_pass(self):
        """Bullets under 22 words should pass word count check."""
        html = _make_resume_html(bullets=[
            "Built backend API serving 10K users",
            "Reduced latency 40% via caching",
            "Led team of 5 engineers",
        ])
        result = validate_resume(html)
        assert result.checks["bullet_word_count"] is True

    def test_long_bullet_fails(self):
        """A bullet over 22 words should fail word count check (as warning)."""
        long_bullet = " ".join(["word"] * 23)
        html = _make_resume_html(bullets=[long_bullet])
        result = validate_resume(html)
        assert result.checks["bullet_word_count"] is False
        assert any("exceed 22 words" in w for w in result.warnings)

    def test_exactly_22_words_passes(self):
        """A bullet with exactly 22 words should pass."""
        bullet_22 = " ".join(["word"] * 22)
        html = _make_resume_html(bullets=[bullet_22])
        result = validate_resume(html)
        assert result.checks["bullet_word_count"] is True

    def test_23_words_fails(self):
        """A bullet with 23 words should fail."""
        bullet_23 = " ".join(["word"] * 23)
        html = _make_resume_html(bullets=[bullet_23])
        result = validate_resume(html)
        assert result.checks["bullet_word_count"] is False

    def test_mixed_bullets_fails_if_any_long(self):
        """If any bullet exceeds 22 words, the check fails."""
        html = _make_resume_html(bullets=[
            "Built API",
            " ".join(["word"] * 25),
            "Shipped feature fast",
        ])
        result = validate_resume(html)
        assert result.checks["bullet_word_count"] is False


class TestCompoundSentences:
    """validate_resume() catches two-achievement bullets."""

    def test_simple_bullet_passes(self):
        """Simple single-achievement bullets should pass."""
        html = _make_resume_html(bullets=[
            "Built backend API serving 10K users",
            "Reduced latency 40% via caching",
        ])
        result = validate_resume(html)
        assert result.checks["no_compound_bullets"] is True

    def test_short_and_passes(self):
        """Short bullets with 'and' are fine (e.g., 'Built and deployed API')."""
        html = _make_resume_html(bullets=[
            "Built and deployed the API",
        ])
        result = validate_resume(html)
        assert result.checks["no_compound_bullets"] is True

    def test_compound_and_detected(self):
        """Long bullet joining two achievements with 'and' is detected."""
        compound = "Led migration to microservices architecture and mentored 3 junior engineers to production readiness improving team velocity"
        assert _is_compound_bullet(compound) is True

    def test_compound_while_detected(self):
        """Long bullet joining two achievements with 'while' is detected."""
        compound = "Redesigned the payment processing pipeline while managing a team of 5 engineers across two time zones"
        assert _is_compound_bullet(compound) is True

    def test_compound_resulting_in_detected(self):
        """Long bullet joining achievements with 'resulting in' is detected."""
        compound = "Implemented new caching layer across all microservices resulting in a 40% reduction in API response times"
        assert _is_compound_bullet(compound) is True

    def test_short_compound_not_flagged(self):
        """Short bullets with conjunctions should not be flagged (< 12 words)."""
        short = "Built and shipped the MVP"
        assert _is_compound_bullet(short) is False


class TestQuantificationDetection:
    """_has_quantified_metric() detects numbers, percentages, and dollar amounts."""

    def test_percentage_detected(self):
        """Bullets with percentages should be detected as quantified."""
        assert _has_quantified_metric("Reduced API latency by 40%") is True

    def test_dollar_amount_detected(self):
        """Bullets with dollar amounts should be detected as quantified."""
        assert _has_quantified_metric("Saved $1.2M in annual infrastructure costs") is True

    def test_multiplier_detected(self):
        """Bullets with multipliers (3x, 10X) should be detected as quantified."""
        assert _has_quantified_metric("Improved throughput 3x via caching") is True

    def test_user_count_detected(self):
        """Bullets with user/customer counts should be detected as quantified."""
        assert _has_quantified_metric("Built API serving 10K users daily") is True

    def test_team_size_detected(self):
        """Bullets mentioning team sizes should be detected as quantified."""
        assert _has_quantified_metric("Led team of 12 engineers") is True

    def test_before_after_detected(self):
        """Bullets with before/after context should be detected as quantified."""
        assert _has_quantified_metric("Cut latency from 3.2s to 0.8s") is True

    def test_time_unit_detected(self):
        """Bullets with time measurements should be detected as quantified."""
        assert _has_quantified_metric("Reduced deploy time to 15 minutes") is True

    def test_no_metric_not_detected(self):
        """Bullets without any metrics should NOT be detected."""
        assert _has_quantified_metric("Built backend API") is False

    def test_vague_bullet_not_detected(self):
        """Vague bullets without numbers should NOT be detected."""
        assert _has_quantified_metric("Improved system performance significantly") is False

    def test_validate_resume_quantification_pass(self):
        """validate_resume() passes when most bullets have metrics."""
        html = _make_resume_html(bullets=[
            "Reduced latency 40% via caching",
            "Built API serving 10K users",
            "Led team of 5 engineers",
            "Saved $500K annually",
        ])
        result = validate_resume(html)
        assert "quantification_rate" in result.checks
        assert result.checks["quantification_rate"] is True

    def test_validate_resume_quantification_warn(self):
        """validate_resume() warns when few bullets have metrics."""
        html = _make_resume_html(bullets=[
            "Built backend API",
            "Improved system performance",
            "Managed cloud infrastructure",
            "Designed new architecture",
        ])
        result = validate_resume(html)
        assert result.checks["quantification_rate"] is False
        assert any("quantified metrics" in w for w in result.warnings)


class TestAITellDetection:
    """detect_ai_tells() finds AI-sounding words and phrases."""

    def test_clean_text_returns_empty(self):
        """Text without AI tells should return empty list."""
        text = "Built API serving 10K daily users. Cut latency from 3.2s to 0.8s."
        assert detect_ai_tells(text) == []

    def test_detects_single_ai_word(self):
        """Should detect a single AI-tell word."""
        text = "Leveraged cloud infrastructure to reduce costs."
        found = detect_ai_tells(text)
        assert "leveraged" in found

    def test_detects_multiple_ai_words(self):
        """Should detect multiple AI-tell words in one text."""
        text = "Spearheaded a robust and seamless migration to cloud."
        found = detect_ai_tells(text)
        assert "spearheaded" in found
        assert "robust" in found
        assert "seamless" in found

    def test_detects_ai_phrase(self):
        """Should detect AI-tell phrases like 'proven track record'."""
        text = "Professional with a proven track record of delivery."
        found = detect_ai_tells(text)
        assert "proven track record" in found

    def test_detects_results_driven(self):
        """Should detect 'results-driven' phrase."""
        text = "Results-driven engineer with 5 years experience."
        found = detect_ai_tells(text)
        assert "results-driven" in found

    def test_case_insensitive(self):
        """Detection should be case insensitive."""
        text = "LEVERAGED advanced techniques and ORCHESTRATED the migration."
        found = detect_ai_tells(text)
        assert "leveraged" in found
        assert "orchestrated" in found

    def test_validate_resume_ai_tells_clean(self):
        """validate_resume() should have ai_tells_clean check for clean resume."""
        html = _make_resume_html(bullets=[
            "Built backend API serving 10K users",
            "Reduced latency 40% via caching",
        ])
        result = validate_resume(html)
        assert "ai_tells_clean" in result.checks
        assert result.checks["ai_tells_clean"] is True

    def test_validate_resume_ai_tells_flagged(self):
        """validate_resume() should flag AI tells in warnings."""
        html = _make_resume_html(
            summary="Innovative engineer with a proven track record.",
            bullets=["Leveraged cloud to streamline operations"],
        )
        result = validate_resume(html)
        assert result.checks["ai_tells_clean"] is False
        assert any("AI-tell" in w for w in result.warnings)


class TestRhythmVariation:
    """_has_rhythm_variation() detects uniform bullet word counts (AI signal)."""

    def test_varied_rhythm_passes(self):
        """Bullets with varied word counts should pass."""
        # 6, 4, 9, 5 words — clearly varied
        assert _has_rhythm_variation([6, 4, 9, 5]) is True

    def test_uniform_rhythm_fails(self):
        """3+ consecutive bullets with same word count should fail."""
        # 8, 8, 8 — too uniform
        assert _has_rhythm_variation([8, 8, 8]) is False

    def test_near_uniform_rhythm_fails(self):
        """3+ consecutive bullets within ±1 word of each other should fail."""
        # 7, 8, 7 — all within ±1 of avg 7.3
        assert _has_rhythm_variation([7, 8, 7]) is False

    def test_uniform_in_middle_fails(self):
        """Uniform window buried in varied bullets should still fail."""
        # Varied, then 3 uniform, then varied
        assert _has_rhythm_variation([5, 12, 8, 8, 9, 3]) is False

    def test_two_bullets_always_passes(self):
        """With fewer than 3 bullets, can't judge rhythm."""
        assert _has_rhythm_variation([8, 8]) is True

    def test_single_bullet_passes(self):
        """Single bullet trivially passes."""
        assert _has_rhythm_variation([10]) is True

    def test_empty_passes(self):
        """No bullets trivially passes."""
        assert _has_rhythm_variation([]) is True

    def test_wide_variation_passes(self):
        """Bullets alternating short/long should pass easily."""
        assert _has_rhythm_variation([4, 12, 5, 14, 3]) is True

    def test_validate_resume_rhythm_pass(self):
        """validate_resume() should pass rhythm for varied bullets."""
        html = _make_resume_html(bullets=[
            "Built API serving 10K users",                    # 6 words
            "Cut latency 40%",                                 # 3 words
            "Led team of 5 engineers on critical migration",  # 9 words
            "Shipped v2",                                      # 2 words
        ])
        result = validate_resume(html)
        assert result.checks["rhythm_variation"] is True

    def test_validate_resume_rhythm_warn(self):
        """validate_resume() should warn when bullets are too uniform."""
        html = _make_resume_html(bullets=[
            "Built backend API serving 10K users daily",       # 7 words
            "Reduced cloud costs across all AWS regions",      # 7 words
            "Led migration from legacy monolith architecture", # 6 words
        ])
        result = validate_resume(html)
        assert result.checks["rhythm_variation"] is False
        assert any("rhythm" in w.lower() for w in result.warnings)


class TestScopeConflation:
    """Detects 'N+ years [narrow-domain]' claims not grounded in source text.

    Catches the hallucination where '8yr SWE + 1yr AI' becomes
    '8+ years building AI-powered products' in the summary.
    """

    def test_extract_years_claim_simple(self):
        """Extracts 'N years domain' from summary text."""
        claims = _detect_summary_years_claim("Engineer with 8 years building AI products.")
        assert len(claims) >= 1
        assert claims[0][0] == 8  # years

    def test_extract_years_claim_plus(self):
        """Extracts 'N+ years domain' with plus sign."""
        claims = _detect_summary_years_claim("Developer with 6+ years of machine learning experience.")
        assert len(claims) >= 1
        assert claims[0][0] == 6

    def test_extract_no_claim_short_years(self):
        """Does not flag claims under 3 years (too common to be conflation)."""
        claims = _detect_summary_years_claim("Engineer with 2 years backend development.")
        assert len(claims) == 0

    def test_grounded_generic_domain(self):
        """Generic domains like 'software engineering' are always grounded."""
        assert _check_years_domain_grounded(8, "software engineering", "I have 2 years of coding")

    def test_grounded_when_domain_frequent(self):
        """Domain mentioned many times in source is grounded."""
        source = "Built ML pipeline. Trained ML models. Deployed ML inference. ML optimization work."
        assert _check_years_domain_grounded(5, "machine learning", source)

    def test_ungrounded_narrow_domain(self):
        """Narrow domain mentioned once in 8yr source is not grounded."""
        source = "8 years software engineering. One project involved AI chatbot."
        assert not _check_years_domain_grounded(8, "building AI-powered products", source)

    def test_ungrounded_ml_one_mention(self):
        """ML mentioned once in long career is not grounded for 6+ years claim."""
        source = "Worked as backend engineer for 6 years. Did one ML side project."
        assert not _check_years_domain_grounded(6, "machine learning", source)

    def test_grounded_no_source(self):
        """Returns True (grounded) when no source text is provided."""
        assert _check_years_domain_grounded(8, "AI products", "")

    def test_validate_resume_scope_conflation_flagged(self):
        """validate_resume() warns when summary years+domain is ungrounded."""
        html = _make_resume_html(
            summary="Full-stack engineer with 8 years building AI-powered products.",
        )
        source = "Software engineer for 8 years. Built one AI chatbot as side project."
        result = validate_resume(html, source_text=source)
        assert result.checks["summary_years_grounded"] is False
        assert any("verify" in w.lower() for w in result.warnings)

    def test_validate_resume_scope_grounded_passes(self):
        """validate_resume() passes when summary domain is well-supported."""
        html = _make_resume_html(
            summary="Backend engineer with 5 years building distributed systems.",
        )
        source = "5 years backend engineering. Built distributed systems at scale."
        result = validate_resume(html, source_text=source)
        assert result.checks["summary_years_grounded"] is True

    def test_validate_resume_no_source_passes(self):
        """validate_resume() passes scope check when no source_text provided."""
        html = _make_resume_html(
            summary="Engineer with 10 years building quantum computers.",
        )
        result = validate_resume(html)  # no source_text
        assert result.checks["summary_years_grounded"] is True


class TestScaleAttribution:
    """Detects employer-scale claims attributed to the candidate.

    Catches hallucination where 'employer serves 2M users' becomes
    'serving millions of users' in the candidate's resume.
    """

    def test_detect_serving_millions(self):
        """Flags 'serving millions of users' not in source."""
        flagged = _detect_ungrounded_scale(
            "Built search feature serving millions of users",
            "Worked at legal tech company. Built internal search."
        )
        assert len(flagged) > 0

    def test_detect_at_scale(self):
        """Flags 'at scale' not in source."""
        flagged = _detect_ungrounded_scale(
            "Deployed services at enterprise scale",
            "Built internal tools for team of 15."
        )
        assert len(flagged) > 0

    def test_no_flag_when_in_source(self):
        """Does not flag scale language that appears in source."""
        flagged = _detect_ungrounded_scale(
            "Built API serving millions of users",
            "Built API serving millions of users at Acme Corp."
        )
        assert len(flagged) == 0

    def test_no_flag_without_scale_language(self):
        """Does not flag resume without scale claims."""
        flagged = _detect_ungrounded_scale(
            "Built internal dashboard for team reporting",
            "Worked on team reporting tools."
        )
        assert len(flagged) == 0

    def test_no_flag_empty_source(self):
        """Returns empty when no source text provided."""
        flagged = _detect_ungrounded_scale(
            "Serving millions of users",
            ""
        )
        assert len(flagged) == 0

    def test_validate_resume_scale_flagged(self):
        """validate_resume() warns when scale claims are ungrounded."""
        html = _make_resume_html(
            bullets=["Built API serving millions of users daily"],
        )
        source = "Worked at legal tech company. Built internal API."
        result = validate_resume(html, source_text=source)
        assert result.checks["no_ungrounded_scale"] is False
        assert any("scale" in w.lower() or "employer" in w.lower() for w in result.warnings)

    def test_validate_resume_no_source_passes(self):
        """validate_resume() passes scale check when no source_text provided."""
        html = _make_resume_html(
            bullets=["Built API serving millions of users daily"],
        )
        result = validate_resume(html)  # no source_text
        assert result.checks["no_ungrounded_scale"] is True


class TestQualityChecksCompleteness:
    """validate_resume() returns all expected check keys for production integration."""

    def test_all_quality_check_keys_present(self):
        """Every expected quality check key should be in result.checks."""
        html = _make_resume_html(bullets=[
            "Built backend API serving 10K users",
            "Reduced latency 40% via caching",
        ])
        result = validate_resume(html)
        expected_keys = {
            "summary_exists", "summary_length", "experience_count",
            "action_verbs", "bullet_word_count", "no_compound_bullets",
            "quantification_rate", "ai_tells_clean", "rhythm_variation",
            "summary_years_grounded", "no_ungrounded_scale",
            "keyword_coverage", "reverse_chronological",
            "skills_section", "education_section",
        }
        assert expected_keys.issubset(set(result.checks.keys())), \
            f"Missing keys: {expected_keys - set(result.checks.keys())}"

    def test_clean_resume_all_checks_pass(self):
        """A well-formed resume with metrics should pass all checks."""
        html = _make_resume_html(
            summary="Backend engineer with 5 years building distributed systems.",
            bullets=[
                "Built API serving 10K daily users",               # 6 words
                "Cut latency 40%",                                  # 3 words
                "Led team of 5 engineers on critical migration",   # 9 words
                "Shipped v2 serving 50K requests per second",      # 7 words
            ],
        )
        result = validate_resume(html)
        for check_name, passed in result.checks.items():
            assert passed, f"Check '{check_name}' should pass for a clean resume"


class TestSummaryLength:
    """validate_resume() catches summaries > 50 words."""

    def test_short_summary_passes(self):
        """Summary under 50 words should pass."""
        summary = "Backend engineer with 5 years building distributed systems."
        html = _make_resume_html(summary=summary)
        result = validate_resume(html)
        assert result.checks["summary_length"] is True

    def test_50_word_summary_passes(self):
        """Summary with exactly 50 words should pass."""
        summary = " ".join(["word"] * 50)
        html = _make_resume_html(summary=summary)
        result = validate_resume(html)
        assert result.checks["summary_length"] is True

    def test_51_word_summary_fails(self):
        """Summary with 51 words should fail."""
        summary = " ".join(["word"] * 51)
        html = _make_resume_html(summary=summary)
        result = validate_resume(html)
        assert result.checks["summary_length"] is False
        assert any("50" in e for e in result.errors)

    def test_100_word_summary_fails(self):
        """Summary with 100 words should fail (was old limit)."""
        summary = " ".join(["word"] * 100)
        html = _make_resume_html(summary=summary)
        result = validate_resume(html)
        assert result.checks["summary_length"] is False


class TestDatasetIntegrity:
    """All samples have required fields; trap samples have dimension expectations."""

    @pytest.fixture
    def samples(self):
        """Load the drafting samples dataset."""
        path = Path(__file__).parent.parent / "evals" / "datasets" / "drafting_samples.json"
        with open(path) as f:
            data = json.load(f)
        return data["samples"]

    def test_total_sample_count(self, samples):
        """Dataset should have 9 samples (5 base + 4 traps)."""
        assert len(samples) == 9

    def test_all_samples_have_profile_text(self, samples):
        """Every sample must have a profile_text field for source fidelity."""
        for sample in samples:
            assert "profile_text" in sample, f"Sample {sample['id']} missing profile_text"
            assert len(sample["profile_text"]) > 50, f"Sample {sample['id']} has short profile_text"

    def test_all_samples_have_required_fields(self, samples):
        """Every sample must have id, profile, job, and expectations."""
        for sample in samples:
            assert "id" in sample
            assert "profile" in sample
            assert "job" in sample
            assert "expectations" in sample

    def test_trap_samples_exist(self, samples):
        """All 4 regression trap samples should exist."""
        trap_ids = {s["id"] for s in samples if s["expectations"].get("trap")}
        expected_traps = {
            "scope-conflation-trap",
            "run-on-sentence-trap",
            "buried-experience-trap",
            "keyword-dilution-trap",
        }
        assert expected_traps == trap_ids

    def test_scope_conflation_trap_has_pattern(self, samples):
        """Scope conflation trap has a regex pattern to check against."""
        trap = next(s for s in samples if s["id"] == "scope-conflation-trap")
        assert "should_NOT_contain_pattern" in trap["expectations"]

    def test_trap_samples_have_dimension_expectations(self, samples):
        """Trap samples specify minimum dimension scores."""
        traps = [s for s in samples if s["expectations"].get("trap")]
        for trap in traps:
            assert "min_dimensions" in trap["expectations"], \
                f"Trap {trap['id']} missing min_dimensions"


class TestGraderDimensions:
    """Grader has 6 dimensions with correct weights."""

    def test_dimension_weights_sum_to_one(self):
        """Dimension weights should sum to 1.0."""
        from evals.graders.drafting_llm_grader import DIMENSION_WEIGHTS
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_six_dimensions_exist(self):
        """Should have exactly 6 dimensions."""
        from evals.graders.drafting_llm_grader import DIMENSION_WEIGHTS
        assert len(DIMENSION_WEIGHTS) == 6

    def test_expected_dimensions(self):
        """All expected dimensions should be present."""
        from evals.graders.drafting_llm_grader import DIMENSION_WEIGHTS
        expected = {
            "source_fidelity", "conciseness", "narrative_hierarchy",
            "narrative_coherence", "job_relevance", "ats_optimization",
        }
        assert set(DIMENSION_WEIGHTS.keys()) == expected

    def test_source_fidelity_highest_weight(self):
        """Source fidelity should have the highest weight (25%)."""
        from evals.graders.drafting_llm_grader import DIMENSION_WEIGHTS
        assert DIMENSION_WEIGHTS["source_fidelity"] == 0.25

    def test_grade_dataclass_fields(self):
        """DraftLLMGrade should have all 6 dimension fields."""
        from evals.graders.drafting_llm_grader import DraftLLMGrade
        grade = DraftLLMGrade(
            source_fidelity=80,
            conciseness=75,
            narrative_hierarchy=70,
            narrative_coherence=72,
            job_relevance=85,
            ats_optimization=90,
            overall_score=78.5,
            strengths=["good"],
            weaknesses=["bad"],
            specific_improvements=["improve"],
            reasoning="test",
        )
        assert grade.source_fidelity == 80
        assert grade.conciseness == 75
        assert grade.narrative_hierarchy == 70
        assert grade.narrative_coherence == 72
        assert grade.job_relevance == 85
        assert grade.ats_optimization == 90


class TestGraderSignature:
    """grade() accepts original_resume_text parameter."""

    def test_grade_accepts_original_resume_text(self):
        """The grade method should accept original_resume_text kwarg."""
        import inspect
        from evals.graders.drafting_llm_grader import DraftingLLMGrader
        sig = inspect.signature(DraftingLLMGrader.grade)
        params = list(sig.parameters.keys())
        assert "original_resume_text" in params

    def test_grade_accepts_discovered_experiences(self):
        """The grade method should accept discovered_experiences kwarg."""
        import inspect
        from evals.graders.drafting_llm_grader import DraftingLLMGrader
        sig = inspect.signature(DraftingLLMGrader.grade)
        params = list(sig.parameters.keys())
        assert "discovered_experiences" in params


class TestDraftGeneratorContext:
    """Draft generator mirrors production pipeline for accurate tuning."""

    def test_draft_generator_accepts_profile_text(self):
        """create_draft_generator's inner function should accept profile_text arg."""
        import inspect
        from evals.run_drafting_tuning import create_draft_generator
        gen = create_draft_generator()
        sig = inspect.signature(gen)
        params = list(sig.parameters.keys())
        assert "profile_text" in params, "Draft generator must accept profile_text for source fidelity"

    def test_draft_generator_profile_text_has_default(self):
        """profile_text should have a default value (empty string) for backward compat."""
        import inspect
        from evals.run_drafting_tuning import create_draft_generator
        gen = create_draft_generator()
        sig = inspect.signature(gen)
        param = sig.parameters["profile_text"]
        assert param.default == "", "profile_text should default to empty string"

    def test_draft_generator_uses_production_context_builder(self):
        """Draft generator should use _build_drafting_context_from_raw (production path)."""
        import inspect
        from evals.run_drafting_tuning import create_draft_generator
        gen = create_draft_generator()
        source = inspect.getsource(gen)
        assert "_build_drafting_context_from_raw" in source, \
            "Draft generator must use production context builder for accurate tuning"

    def test_draft_generator_uses_production_message_format(self):
        """Draft generator should send the same user message format as production."""
        import inspect
        from evals.run_drafting_tuning import create_draft_generator
        gen = create_draft_generator()
        source = inspect.getsource(gen)
        assert "Create an ATS-optimized resume based on:" in source, \
            "Draft generator must use same user message as production drafting node"

    def test_draft_generator_extracts_html_from_code_blocks(self):
        """Draft generator should extract HTML from code fences like production."""
        import inspect
        from evals.run_drafting_tuning import create_draft_generator
        gen = create_draft_generator()
        source = inspect.getsource(gen)
        assert "_extract_content_from_code_block" in source, \
            "Draft generator must extract HTML from code blocks like production"


class TestTuningLoopDimensions:
    """Tuning loop uses the correct 6 dimensions."""

    def test_tuning_loop_has_6_dimensions(self):
        """DIMENSIONS list should have 6 entries."""
        from evals.drafting_tuning_loop import DIMENSIONS
        assert len(DIMENSIONS) == 6

    def test_tuning_loop_dimensions_match_grader(self):
        """Tuning loop dimensions should match grader dimensions."""
        from evals.drafting_tuning_loop import DIMENSIONS
        from evals.graders.drafting_llm_grader import DIMENSION_WEIGHTS
        assert set(DIMENSIONS) == set(DIMENSION_WEIGHTS.keys())

    def test_target_improvement_is_10_percent(self):
        """Target improvement should be 0.10 (10%)."""
        from evals.drafting_tuning_loop import TARGET_IMPROVEMENT
        assert TARGET_IMPROVEMENT == 0.10


class TestKeywordCoverage:
    """_extract_job_keywords() and keyword_coverage check in validate_resume()."""

    def test_extracts_tech_terms(self):
        """Should extract common technology names from job text."""
        job_text = "We need someone with Python, React, and AWS experience."
        keywords = _extract_job_keywords(job_text)
        assert "python" in keywords
        assert "react" in keywords
        assert "aws" in keywords

    def test_extracts_acronyms(self):
        """Should extract uppercase acronyms like CI/CD, GCP."""
        job_text = "Experience with CI/CD pipelines and GCP infrastructure."
        keywords = _extract_job_keywords(job_text)
        assert "ci/cd" in keywords
        assert "gcp" in keywords

    def test_extracts_multi_word_tech(self):
        """Should extract multi-word tech terms like machine learning."""
        job_text = "Strong background in machine learning and distributed systems."
        keywords = _extract_job_keywords(job_text)
        assert "machine learning" in keywords
        assert "distributed systems" in keywords

    def test_filters_stop_words(self):
        """Should not include generic stop words."""
        job_text = "The ideal candidate should have strong experience working in a team."
        keywords = _extract_job_keywords(job_text)
        assert "the" not in keywords
        assert "and" not in keywords
        assert "experience" not in keywords

    def test_empty_job_text(self):
        """Empty job text returns empty list."""
        assert _extract_job_keywords("") == []

    def test_extracts_experience_with_pattern(self):
        """Should extract terms after 'experience with/in' patterns."""
        job_text = "Must have experience with kubernetes, terraform, and docker."
        keywords = _extract_job_keywords(job_text)
        assert "kubernetes" in keywords
        assert "terraform" in keywords
        assert "docker" in keywords

    def test_validate_resume_keyword_coverage_passes(self):
        """Resume with matching keywords passes coverage check."""
        html = _make_resume_html(
            summary="Backend engineer with 5 years building distributed systems.",
            bullets=[
                "Built Python API serving 10K users",
                "Deployed to AWS with Docker containers",
                "Cut latency 40% via Redis caching",
            ],
        )
        job_text = "Python backend engineer with AWS and Docker experience."
        result = validate_resume(html, job_text=job_text)
        assert result.checks["keyword_coverage"] is True

    def test_validate_resume_keyword_coverage_fails(self):
        """Resume missing key job terms fails coverage check."""
        html = _make_resume_html(
            summary="Marketing manager with 5 years experience.",
            bullets=[
                "Led social media campaigns for brand awareness",
                "Managed team of 3 content writers",
            ],
        )
        job_text = "Senior Python engineer with React, AWS, Docker, Kubernetes, and PostgreSQL."
        result = validate_resume(html, job_text=job_text)
        assert result.checks["keyword_coverage"] is False

    def test_validate_resume_no_job_text_passes(self):
        """No job text means keyword coverage check passes by default."""
        html = _make_resume_html(bullets=["Built API serving 10K users"])
        result = validate_resume(html, job_text="")
        assert result.checks["keyword_coverage"] is True

    def test_coverage_warning_includes_missing_terms(self):
        """Warning message should list missing key terms."""
        html = _make_resume_html(
            summary="Java developer with 3 years experience.",
            bullets=["Built Java backend for internal tools"],
        )
        job_text = "We need Python, React, AWS, and Docker experience."
        result = validate_resume(html, job_text=job_text)
        if not result.checks["keyword_coverage"]:
            low_coverage_warnings = [w for w in result.warnings if "keyword coverage" in w.lower()]
            assert len(low_coverage_warnings) > 0


def _make_multi_experience_html(roles: list[dict]) -> str:
    """Build resume HTML with multiple experience entries.

    Args:
        roles: List of dicts with 'title', 'company', 'dates', 'bullets'.
    """
    sections = [
        '<h1>Test Candidate</h1>',
        '<p>test@email.com | 555-1234</p>',
        '<h2>Professional Summary</h2>',
        '<p>Software engineer with 5 years experience.</p>',
        '<h2>Experience</h2>',
    ]
    for role in roles:
        sections.append(f'<h3>{role["title"]} | {role["company"]} | {role["dates"]}</h3>')
        bullet_html = "\n".join(f'<li>{b}</li>' for b in role.get("bullets", ["Built software"]))
        sections.append(f'<ul>{bullet_html}</ul>')
    sections.append('<h2>Skills</h2>')
    sections.append('<p>Python, JavaScript</p>')
    sections.append('<h2>Education</h2>')
    sections.append('<p><strong>BS CS</strong> - University, 2018</p>')
    return "\n".join(sections)


class TestReverseChronological:
    """_extract_experience_years() and reverse_chronological check in validate_resume()."""

    def test_extracts_years_from_entries(self):
        """Should extract year from experience h3 entries."""
        html = """<h3>Engineer | Company A | 2022-Present</h3>
                   <h3>Developer | Company B | 2019-2022</h3>"""
        entries = _extract_experience_years(html)
        assert len(entries) == 2
        assert entries[0][1] == 9999  # "Present" maps to 9999
        assert entries[1][1] == 2022

    def test_current_role_sorts_first(self):
        """Role with 'Present' should have highest sort year."""
        html = '<h3>Engineer | Company | 2020-Present</h3>'
        entries = _extract_experience_years(html)
        assert entries[0][1] == 9999

    def test_handles_no_dates(self):
        """Entries without years get None."""
        html = '<h3>Engineer | Company</h3>'
        entries = _extract_experience_years(html)
        assert entries[0][1] is None

    def test_reverse_chrono_passes(self):
        """Resume with newest-first ordering passes check."""
        html = _make_multi_experience_html([
            {"title": "Senior Engineer", "company": "NewCo", "dates": "2022-Present",
             "bullets": ["Led team of 5 engineers"]},
            {"title": "Engineer", "company": "OldCo", "dates": "2019-2022",
             "bullets": ["Built backend API serving users"]},
            {"title": "Intern", "company": "StartCo", "dates": "2018-2019",
             "bullets": ["Shipped first production feature"]},
        ])
        result = validate_resume(html)
        assert result.checks["reverse_chronological"] is True

    def test_wrong_order_fails(self):
        """Resume with oldest-first ordering fails check."""
        html = _make_multi_experience_html([
            {"title": "Intern", "company": "StartCo", "dates": "2018-2019",
             "bullets": ["Shipped first production feature"]},
            {"title": "Engineer", "company": "OldCo", "dates": "2019-2022",
             "bullets": ["Built backend API serving users"]},
            {"title": "Senior Engineer", "company": "NewCo", "dates": "2022-Present",
             "bullets": ["Led team of 5 engineers"]},
        ])
        result = validate_resume(html)
        assert result.checks["reverse_chronological"] is False

    def test_single_entry_passes(self):
        """Single experience entry always passes."""
        html = _make_resume_html(bullets=["Built API serving 10K users"])
        result = validate_resume(html)
        assert result.checks["reverse_chronological"] is True

    def test_warning_on_wrong_order(self):
        """Should produce warning when not reverse chronological."""
        html = _make_multi_experience_html([
            {"title": "Junior Dev", "company": "A", "dates": "2015-2017",
             "bullets": ["Wrote tests for legacy code"]},
            {"title": "Senior Dev", "company": "B", "dates": "2020-Present",
             "bullets": ["Led architecture redesign effort"]},
        ])
        result = validate_resume(html)
        chrono_warnings = [w for w in result.warnings if "chronological" in w.lower()]
        assert len(chrono_warnings) > 0


class TestFullPipelineIntegration:
    """End-to-end integration: validate_resume() with all three inputs."""

    def test_good_resume_all_checks_pass(self):
        """A well-crafted resume with source and job should pass all checks."""
        html = _make_multi_experience_html([
            {"title": "Senior Engineer", "company": "Acme Corp", "dates": "2021-Present",
             "bullets": [
                 "Built Python API serving 50K daily users",
                 "Cut deploy time from 2hr to 15min",
                 "Led team of 4 engineers on core migration",
             ]},
            {"title": "Engineer", "company": "StartupCo", "dates": "2018-2021",
             "bullets": [
                 "Shipped React frontend used by 10K users",
                 "Automated CI/CD pipeline with Docker",
             ]},
        ])
        source = """Senior Software Engineer at Acme Corp. Built Python API serving 50K daily users.
        Cut deploy time from 2hr to 15min. Led team of 4 engineers.
        Previously at StartupCo. Built React frontend. Set up CI/CD with Docker."""
        job = "Senior Python engineer with experience in React, Docker, and AWS. 5+ years experience."
        result = validate_resume(html, source_text=source, job_text=job)
        # Core structural checks should pass
        assert result.checks["summary_exists"] is True
        assert result.checks["experience_count"] is True
        assert result.checks["skills_section"] is True
        assert result.checks["education_section"] is True
        assert result.checks["reverse_chronological"] is True
        assert result.checks["bullet_word_count"] is True
        assert result.checks["no_ungrounded_scale"] is True

    def test_hallucinating_resume_caught(self):
        """Resume with scope conflation + scale attribution should be flagged."""
        html = """<h1>Test Candidate</h1>
        <p>test@email.com</p>
        <h2>Professional Summary</h2>
        <p>AI engineer with 8+ years building AI-powered products, serving millions of users.</p>
        <h2>Experience</h2>
        <h3>Engineer | BigCo | 2016-Present</h3>
        <ul>
        <li>Built ML models serving millions of users</li>
        <li>Led AI team of 20 engineers</li>
        </ul>
        <h2>Skills</h2><p>Python</p>
        <h2>Education</h2><p><strong>BS CS</strong> - University, 2016</p>"""
        source = """Software engineer at BigCo (2016-present). 8 years general SWE.
        1 year on ML side project. BigCo serves millions of users."""
        result = validate_resume(html, source_text=source)
        # Should flag scope conflation (8+ years AI when only 1yr actual)
        assert result.checks["summary_years_grounded"] is False
        # Should flag scale attribution (serving millions is company's scale)
        assert result.checks["no_ungrounded_scale"] is False

    def test_keyword_poor_resume_flagged(self):
        """Resume missing key job terms should fail keyword coverage."""
        html = _make_resume_html(
            summary="Marketing professional with 5 years experience.",
            bullets=["Managed social media campaigns for clients"],
        )
        job = "Looking for a Python developer with React, Docker, Kubernetes, and AWS experience."
        result = validate_resume(html, job_text=job)
        assert result.checks["keyword_coverage"] is False

    def test_all_18_checks_present(self):
        """Every call to validate_resume should return all 18 check keys."""
        html = _make_resume_html()
        result = validate_resume(html, source_text="some source", job_text="Python developer")
        expected_keys = {
            "summary_exists", "summary_length", "experience_count",
            "action_verbs", "bullet_word_count", "no_compound_bullets",
            "quantification_rate", "ai_tells_clean", "rhythm_variation",
            "summary_years_grounded", "no_ungrounded_scale",
            "keyword_coverage", "reverse_chronological",
            "skills_section", "education_section",
            "no_excessive_em_dashes", "varied_bullet_openings",
            "bullets_per_role",
        }
        assert len(result.checks) >= 18, f"Expected >= 18 checks, got {len(result.checks)}: {list(result.checks.keys())}"
        missing = expected_keys - set(result.checks.keys())
        assert not missing, f"Missing check keys: {missing}"


class TestEmDashDetection:
    """_count_em_dashes() and validate_resume() catch excessive em/en dashes."""

    def test_no_dashes_returns_zero(self):
        assert _count_em_dashes("Built API serving 10K users") == 0

    def test_counts_em_dashes(self):
        assert _count_em_dashes("Led migration \u2014 cutting deploy time 75%") == 1

    def test_counts_en_dashes(self):
        assert _count_em_dashes("2020\u20132023") == 1

    def test_counts_mixed_dashes(self):
        text = "Led migration \u2014 cut time 75%. Dates: 2020\u20132023. Built API \u2014 serving 10K."
        assert _count_em_dashes(text) == 3

    def test_clean_resume_passes(self):
        html = _make_resume_html(
            bullets=["Cut deploy time 75% via Docker", "Built caching layer with Redis"],
        )
        result = validate_resume(html)
        assert result.checks["no_excessive_em_dashes"] is True

    def test_resume_with_excessive_dashes_fails(self):
        html = _make_resume_html(
            bullets=[
                "Led migration \u2014 cutting deploy time 75%",
                "Built API \u2014 serving 10K users daily",
                "Designed system \u2014 reducing latency 40%",
            ],
        )
        result = validate_resume(html)
        assert result.checks["no_excessive_em_dashes"] is False
        assert any("em/en dashes" in w for w in result.warnings)

    def test_two_dashes_still_passes(self):
        html = _make_resume_html(
            bullets=[
                "Led migration \u2014 cutting deploy time 75%",
                "Built API \u2014 serving 10K users daily",
            ],
        )
        result = validate_resume(html)
        assert result.checks["no_excessive_em_dashes"] is True


class TestRepetitiveBulletOpenings:
    """_detect_repetitive_bullet_openings() catches 3+ bullets starting with same verb."""

    def test_varied_openings_clean(self):
        bullets = ["<li>Built API</li>", "<li>Designed caching</li>", "<li>Launched monitoring</li>"]
        assert _detect_repetitive_bullet_openings(bullets) == []

    def test_three_same_opening_flagged(self):
        bullets = ["<li>Built API</li>", "<li>Built caching</li>", "<li>Built monitoring</li>"]
        result = _detect_repetitive_bullet_openings(bullets)
        assert "built" in result

    def test_case_insensitive(self):
        bullets = ["<li>built API</li>", "<li>Built caching</li>", "<li>BUILT monitoring</li>"]
        result = _detect_repetitive_bullet_openings(bullets)
        assert "built" in result

    def test_two_same_opening_ok(self):
        bullets = ["<li>Built API</li>", "<li>Built caching</li>", "<li>Designed system</li>"]
        assert _detect_repetitive_bullet_openings(bullets) == []

    def test_validate_resume_passes_varied(self):
        html = _make_resume_html(
            bullets=["Built API serving 10K users", "Designed caching for search", "Launched monitoring dashboard"],
        )
        result = validate_resume(html)
        assert result.checks["varied_bullet_openings"] is True

    def test_validate_resume_fails_repetitive(self):
        html = _make_resume_html(
            bullets=[
                "Built backend API serving 10K users",
                "Built caching layer with Redis",
                "Built monitoring dashboard for ops",
            ],
        )
        result = validate_resume(html)
        assert result.checks["varied_bullet_openings"] is False
        assert any("repeatedly start with" in w for w in result.warnings)


class TestBulletsPerRole:
    """_count_bullets_per_role() and validate_resume() check 3-5 bullets per role."""

    def test_single_role_extraction(self):
        html = """
        <h3>Engineer | Company | 2020-Present</h3>
        <ul><li>Built API</li><li>Designed cache</li><li>Launched monitor</li></ul>
        """
        result = _count_bullets_per_role(html)
        assert len(result) == 1
        assert result[0][1] == 3

    def test_multiple_roles(self):
        html = """
        <h3>Senior Engineer | BigCo | 2022-Present</h3>
        <ul><li>A</li><li>B</li><li>C</li><li>D</li></ul>
        <h3>Engineer | SmallCo | 2019-2022</h3>
        <ul><li>E</li><li>F</li><li>G</li></ul>
        """
        result = _count_bullets_per_role(html)
        assert len(result) == 2
        assert result[0][1] == 4
        assert result[1][1] == 3

    def test_validate_resume_passes_3_bullets(self):
        html = _make_resume_html(
            bullets=["Built API serving 10K users", "Designed caching layer", "Launched monitoring tool"],
        )
        result = validate_resume(html)
        assert result.checks["bullets_per_role"] is True

    def test_validate_resume_fails_too_few_bullets(self):
        html = _make_resume_html(
            bullets=["Built API serving 10K users"],
        )
        result = validate_resume(html)
        assert result.checks["bullets_per_role"] is False
        assert any("only 1 bullet" in w for w in result.warnings)

    def test_validate_resume_fails_too_many_bullets(self):
        html = _make_resume_html(
            bullets=[
                "Built API serving 10K users",
                "Designed caching layer with Redis",
                "Launched monitoring dashboard for ops",
                "Cut deploy time 75% via Docker",
                "Grew team from 3 to 8",
                "Shipped mobile app in 6 weeks",
            ],
        )
        result = validate_resume(html)
        assert result.checks["bullets_per_role"] is False
        assert any("6 bullets" in w for w in result.warnings)

    def test_five_bullets_passes(self):
        html = _make_resume_html(
            bullets=[
                "Built API serving 10K users",
                "Designed caching layer with Redis",
                "Launched monitoring dashboard for ops",
                "Cut deploy time 75% via Docker",
                "Grew team from 3 to 8",
            ],
        )
        result = validate_resume(html)
        assert result.checks["bullets_per_role"] is True
