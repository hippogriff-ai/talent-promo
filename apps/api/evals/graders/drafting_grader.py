"""Grader for drafting stage outputs.

Evaluates resume drafts on:
- Preference adherence (tone, structure, first person usage)
- Content quality (action verbs, quantification, keywords)
- ATS compatibility (formatting, length)
"""

import re
from dataclasses import dataclass


@dataclass
class DraftScore:
    """Score for a draft evaluation."""
    preference_adherence: float  # 0-1 score for preference matching
    content_quality: float  # 0-1 score for content quality
    ats_compatibility: float  # 0-1 score for ATS compatibility
    overall: float  # Weighted average
    feedback: list[str]  # List of feedback items


class DraftingGrader:
    """Grader for evaluating resume draft quality."""

    # Action verbs that indicate strong writing
    ACTION_VERBS = {
        "led", "managed", "developed", "created", "implemented",
        "designed", "built", "launched", "achieved", "increased",
        "reduced", "improved", "delivered", "established", "spearheaded",
        "orchestrated", "executed", "transformed", "optimized", "streamlined"
    }

    # Formal tone indicators
    FORMAL_INDICATORS = {
        "implemented", "executed", "facilitated", "spearheaded",
        "orchestrated", "established", "demonstrated", "administered"
    }

    # Conversational tone indicators
    CONVERSATIONAL_INDICATORS = {
        "helped", "worked on", "got", "made", "did", "was part of"
    }

    def grade(
        self,
        draft_html: str,
        preferences: dict | None = None,
        job_keywords: list[str] | None = None
    ) -> DraftScore:
        """Grade a resume draft.

        Args:
            draft_html: The HTML content of the resume draft
            preferences: User preferences dict (tone, structure, etc.)
            job_keywords: Keywords from job posting that should be included

        Returns:
            DraftScore with detailed scores and feedback
        """
        feedback = []
        preferences = preferences or {}
        job_keywords = job_keywords or []

        # Extract text from HTML
        text = self._extract_text(draft_html)
        text_lower = text.lower()

        # Score preference adherence
        pref_score, pref_feedback = self._score_preferences(text, text_lower, preferences)
        feedback.extend(pref_feedback)

        # Score content quality
        content_score, content_feedback = self._score_content(text, text_lower)
        feedback.extend(content_feedback)

        # Score ATS compatibility (pass original HTML for tag detection)
        ats_score, ats_feedback = self._score_ats(draft_html, text_lower, job_keywords)
        feedback.extend(ats_feedback)

        # Calculate weighted overall score
        overall = (pref_score * 0.3) + (content_score * 0.4) + (ats_score * 0.3)

        return DraftScore(
            preference_adherence=round(pref_score, 2),
            content_quality=round(content_score, 2),
            ats_compatibility=round(ats_score, 2),
            overall=round(overall, 2),
            feedback=feedback
        )

    def _extract_text(self, html: str) -> str:
        """Extract plain text from HTML."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _score_preferences(self, text: str, text_lower: str, preferences: dict) -> tuple[float, list[str]]:
        """Score how well the draft adheres to user preferences."""
        scores = []
        feedback = []

        # Check tone preference
        if tone := preferences.get("tone"):
            is_formal = any(word in text_lower for word in self.FORMAL_INDICATORS)
            is_conversational = any(phrase in text_lower for phrase in self.CONVERSATIONAL_INDICATORS)

            if tone == "formal":
                score = 1.0 if is_formal and not is_conversational else (0.5 if is_formal else 0.0)
                if score < 1.0:
                    feedback.append("Draft could use more formal tone")
            elif tone == "conversational":
                score = 1.0 if is_conversational and not is_formal else (0.5 if is_conversational else 0.0)
                if score < 1.0:
                    feedback.append("Draft could use more conversational tone")
            else:
                score = 0.5
            scores.append(score)

        # Check first person preference
        if (first_person := preferences.get("first_person")) is not None:
            has_first_person = bool(re.search(r'\bI\b', text))
            if first_person:
                score = 1.0 if has_first_person else 0.0
                if not has_first_person:
                    feedback.append("Draft should use first person (I)")
            else:
                score = 1.0 if not has_first_person else 0.0
                if has_first_person:
                    feedback.append("Draft should avoid first person")
            scores.append(score)

        # Check quantification preference
        if quant := preferences.get("quantification_preference"):
            has_numbers = bool(re.search(r'\d+%|\d+x|\$\d+|\d+ (team|people|users|customers)', text_lower))
            if quant == "heavy_metrics":
                score = 1.0 if has_numbers else 0.3
                if not has_numbers:
                    feedback.append("Draft needs more quantified achievements")
            elif quant == "qualitative":
                score = 1.0 if not has_numbers else 0.5
            else:  # balanced
                score = 0.8
            scores.append(score)

        return (sum(scores) / len(scores) if scores else 0.7), feedback

    def _score_content(self, text: str, text_lower: str) -> tuple[float, list[str]]:
        """Score content quality."""
        scores = []
        feedback = []

        # Check for action verbs
        words = set(text_lower.split())
        action_verb_count = len(words & self.ACTION_VERBS)
        action_score = min(1.0, action_verb_count / 5)  # Expect at least 5 action verbs
        scores.append(action_score)
        if action_score < 0.6:
            feedback.append(f"Use more action verbs (found {action_verb_count}, expect 5+)")

        # Check for quantification
        quant_matches = re.findall(r'\d+%|\d+x|\$[\d,]+|\d+ (team|people|users|customers|projects)', text_lower)
        quant_score = min(1.0, len(quant_matches) / 3)
        scores.append(quant_score)
        if quant_score < 0.6:
            feedback.append(f"Add more quantified achievements (found {len(quant_matches)})")

        # Check content length
        word_count = len(text.split())
        if word_count < 200:
            length_score = 0.5
            feedback.append("Resume is too short")
        elif word_count > 800:
            length_score = 0.7
            feedback.append("Resume may be too long")
        else:
            length_score = 1.0
        scores.append(length_score)

        return sum(scores) / len(scores), feedback

    def _score_ats(self, html: str, text_lower: str, keywords: list[str]) -> tuple[float, list[str]]:
        """Score ATS compatibility.

        Args:
            html: Original HTML content (for tag detection)
            text_lower: Lowercase extracted text (for keyword checking)
            keywords: Job keywords to check coverage
        """
        scores = []
        feedback = []

        # Check keyword coverage
        if keywords:
            found = sum(1 for kw in keywords if kw.lower() in text_lower)
            coverage = found / len(keywords)
            scores.append(coverage)
            if coverage < 0.5:
                missing = [kw for kw in keywords if kw.lower() not in text_lower][:3]
                feedback.append(f"Missing keywords: {', '.join(missing)}")

        # Check for common ATS issues (check original HTML for tags)
        html_lower = html.lower()
        has_tables = '<table' in html_lower
        has_images = '<img' in html_lower

        if has_tables or has_images:
            scores.append(0.5)
            feedback.append("Avoid tables and images for ATS compatibility")
        else:
            scores.append(1.0)

        return (sum(scores) / len(scores) if scores else 0.8), feedback
