"""Programmatic comparison for structured extraction outputs.

Compares actual output to expected output field-by-field and produces:
- Overall completeness score (0-100%)
- Per-field scores
- List of missing fields
- List of wrong values
- List of extra fields (not in expected)
"""

from dataclasses import dataclass, field
from typing import Any
from difflib import SequenceMatcher


@dataclass
class FieldComparison:
    """Comparison result for a single field."""
    field_path: str
    expected: Any
    actual: Any
    score: float  # 0.0 - 1.0
    issue: str | None = None  # Description of mismatch


@dataclass
class ComparisonReport:
    """Full comparison report between actual and expected outputs."""
    overall_score: float  # 0.0 - 1.0 (percentage)
    field_scores: dict[str, float]
    missing_fields: list[str]
    wrong_values: list[FieldComparison]
    extra_fields: list[str]
    total_fields: int
    matched_fields: int

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Overall Score: {self.overall_score * 100:.1f}%",
            f"Fields: {self.matched_fields}/{self.total_fields} matched",
        ]

        if self.missing_fields:
            lines.append(f"\nMISSING ({len(self.missing_fields)}):")
            for f in self.missing_fields[:10]:
                lines.append(f"  - {f}")
            if len(self.missing_fields) > 10:
                lines.append(f"  ... and {len(self.missing_fields) - 10} more")

        if self.wrong_values:
            lines.append(f"\nWRONG VALUES ({len(self.wrong_values)}):")
            for fc in self.wrong_values[:10]:
                lines.append(f"  - {fc.field_path}: {fc.issue}")
            if len(self.wrong_values) > 10:
                lines.append(f"  ... and {len(self.wrong_values) - 10} more")

        if self.extra_fields:
            lines.append(f"\nEXTRA FIELDS ({len(self.extra_fields)}):")
            for f in self.extra_fields[:5]:
                lines.append(f"  + {f}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_score": self.overall_score,
            "field_scores": self.field_scores,
            "missing_fields": self.missing_fields,
            "wrong_values": [
                {
                    "field": fc.field_path,
                    "expected": fc.expected,
                    "actual": fc.actual,
                    "score": fc.score,
                    "issue": fc.issue,
                }
                for fc in self.wrong_values
            ],
            "extra_fields": self.extra_fields,
            "total_fields": self.total_fields,
            "matched_fields": self.matched_fields,
        }


class StructuredComparator:
    """Compare structured extraction outputs programmatically."""

    def __init__(self, string_similarity_threshold: float = 0.8):
        """
        Args:
            string_similarity_threshold: Minimum similarity ratio for fuzzy string matching
        """
        self.string_threshold = string_similarity_threshold

    def compare(self, actual: dict, expected: dict) -> ComparisonReport:
        """Compare actual output to expected output.

        Args:
            actual: The LLM/extraction output
            expected: The ground truth expected output

        Returns:
            ComparisonReport with detailed comparison results
        """
        field_scores = {}
        missing_fields = []
        wrong_values = []
        extra_fields = []

        # Compare all expected fields
        self._compare_dict(actual, expected, "", field_scores, missing_fields, wrong_values)

        # Find extra fields not in expected
        self._find_extra_fields(actual, expected, "", extra_fields)

        # Calculate overall score
        total_fields = len(field_scores)
        if total_fields == 0:
            overall_score = 0.0
        else:
            overall_score = sum(field_scores.values()) / total_fields

        matched_fields = sum(1 for s in field_scores.values() if s >= 0.95)

        return ComparisonReport(
            overall_score=overall_score,
            field_scores=field_scores,
            missing_fields=missing_fields,
            wrong_values=wrong_values,
            extra_fields=extra_fields,
            total_fields=total_fields,
            matched_fields=matched_fields,
        )

    def _compare_dict(
        self,
        actual: dict | None,
        expected: dict,
        path: str,
        field_scores: dict,
        missing_fields: list,
        wrong_values: list,
    ):
        """Recursively compare dictionaries."""
        if actual is None:
            actual = {}

        for key, exp_value in expected.items():
            field_path = f"{path}.{key}" if path else key

            if key not in actual:
                missing_fields.append(field_path)
                field_scores[field_path] = 0.0
                continue

            act_value = actual[key]
            score, issue = self._compare_values(act_value, exp_value, field_path)
            field_scores[field_path] = score

            if score < 1.0 and issue:
                wrong_values.append(FieldComparison(
                    field_path=field_path,
                    expected=exp_value,
                    actual=act_value,
                    score=score,
                    issue=issue,
                ))

    def _compare_values(self, actual: Any, expected: Any, path: str) -> tuple[float, str | None]:
        """Compare two values and return score + issue description."""
        # Handle None
        if expected is None:
            return (1.0, None) if actual is None else (0.5, "Expected None")

        if actual is None:
            return (0.0, "Got None, expected value")

        # Type mismatch
        if type(actual) != type(expected):
            # Allow some flexibility
            if isinstance(expected, str) and actual is not None:
                actual = str(actual)
            elif isinstance(expected, list) and not isinstance(actual, list):
                return (0.0, f"Expected list, got {type(actual).__name__}")
            elif isinstance(expected, dict) and not isinstance(actual, dict):
                return (0.0, f"Expected dict, got {type(actual).__name__}")

        # Compare by type
        if isinstance(expected, str):
            return self._compare_strings(actual, expected)
        elif isinstance(expected, list):
            return self._compare_lists(actual, expected, path)
        elif isinstance(expected, dict):
            return self._compare_nested_dict(actual, expected, path)
        elif isinstance(expected, bool):
            return (1.0, None) if actual == expected else (0.0, f"Expected {expected}, got {actual}")
        elif isinstance(expected, (int, float)):
            return (1.0, None) if actual == expected else (0.5, f"Expected {expected}, got {actual}")
        else:
            return (1.0, None) if actual == expected else (0.0, f"Mismatch: {actual} vs {expected}")

    def _compare_strings(self, actual: str, expected: str) -> tuple[float, str | None]:
        """Compare strings with fuzzy matching."""
        if not actual:
            return (0.0, "Empty string")

        # Normalize
        act_norm = actual.strip().lower()
        exp_norm = expected.strip().lower()

        if act_norm == exp_norm:
            return (1.0, None)

        # Fuzzy match
        ratio = SequenceMatcher(None, act_norm, exp_norm).ratio()
        if ratio >= self.string_threshold:
            return (ratio, f"Fuzzy match: {ratio:.2f}")

        # Check if expected is contained in actual (or vice versa)
        if exp_norm in act_norm or act_norm in exp_norm:
            return (0.8, "Partial match (substring)")

        return (ratio, f"Low similarity: {ratio:.2f}")

    def _compare_lists(self, actual: list, expected: list, path: str) -> tuple[float, str | None]:
        """Compare lists with order-independent matching for strings."""
        if not expected:
            return (1.0, None) if not actual else (0.8, "Expected empty list")

        if not actual:
            return (0.0, f"Empty list, expected {len(expected)} items")

        # For string lists, use set intersection
        if all(isinstance(x, str) for x in expected):
            exp_set = {str(x).strip().lower() for x in expected}
            act_set = {str(x).strip().lower() for x in actual}

            matched = exp_set & act_set
            missing = exp_set - act_set

            if not exp_set:
                return (1.0, None)

            score = len(matched) / len(exp_set)
            if missing:
                return (score, f"Missing {len(missing)}/{len(exp_set)}: {list(missing)[:3]}")
            return (score, None)

        # For dict lists (like experience), compare by length
        if all(isinstance(x, dict) for x in expected):
            if len(actual) >= len(expected):
                return (1.0, None)
            score = len(actual) / len(expected)
            return (score, f"Got {len(actual)}/{len(expected)} items")

        # Generic list comparison
        if len(actual) >= len(expected):
            return (1.0, None)
        return (len(actual) / len(expected), f"Got {len(actual)}/{len(expected)} items")

    def _compare_nested_dict(self, actual: dict, expected: dict, path: str) -> tuple[float, str | None]:
        """Compare nested dictionaries."""
        if not expected:
            return (1.0, None)

        scores = []
        for key, exp_val in expected.items():
            if key not in actual:
                scores.append(0.0)
            else:
                score, _ = self._compare_values(actual[key], exp_val, f"{path}.{key}")
                scores.append(score)

        if not scores:
            return (1.0, None)

        avg_score = sum(scores) / len(scores)
        missing_count = sum(1 for s in scores if s == 0)
        if missing_count > 0:
            return (avg_score, f"Missing {missing_count}/{len(expected)} nested fields")
        return (avg_score, None)

    def _find_extra_fields(self, actual: dict | None, expected: dict, path: str, extra_fields: list):
        """Find fields in actual that aren't in expected."""
        if actual is None:
            return

        for key in actual:
            field_path = f"{path}.{key}" if path else key
            if key not in expected:
                extra_fields.append(field_path)
            elif isinstance(actual[key], dict) and isinstance(expected.get(key), dict):
                self._find_extra_fields(actual[key], expected[key], field_path, extra_fields)
