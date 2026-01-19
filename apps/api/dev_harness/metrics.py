"""Metrics for evaluating LLM extraction quality.

Provides:
- Completeness scoring (% of expected fields present)
- Field-level accuracy comparison
- Latency measurement
- Cost estimation
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class ExtractionResult:
    """Result of a single extraction run."""
    sample_id: str
    model: str
    prompt_version: str
    output: dict
    expected: dict
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Computed metrics
    completeness_score: float = 0.0
    field_scores: dict = field(default_factory=dict)
    missing_fields: list = field(default_factory=list)
    extra_fields: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def compute_completeness(output: dict, expected: dict, path: str = "") -> tuple[float, dict, list]:
    """Compute completeness score by comparing output to expected.

    Returns:
        tuple of (score, field_scores, missing_fields)
        - score: 0.0-1.0, percentage of expected fields present
        - field_scores: dict mapping field names to their scores
        - missing_fields: list of missing field paths
    """
    if not expected:
        return 1.0, {}, []

    total_fields = 0
    present_fields = 0
    field_scores = {}
    missing_fields = []

    for key, expected_value in expected.items():
        field_path = f"{path}.{key}" if path else key
        total_fields += 1

        if key not in output:
            missing_fields.append(field_path)
            field_scores[field_path] = 0.0
            continue

        output_value = output[key]

        # Handle different value types
        if expected_value is None:
            # None expected - any value is fine
            field_scores[field_path] = 1.0
            present_fields += 1

        elif isinstance(expected_value, dict):
            # Recurse into nested dict
            if isinstance(output_value, dict):
                nested_score, nested_fields, nested_missing = compute_completeness(
                    output_value, expected_value, field_path
                )
                field_scores[field_path] = nested_score
                field_scores.update(nested_fields)
                missing_fields.extend(nested_missing)
                present_fields += nested_score
            else:
                field_scores[field_path] = 0.0
                missing_fields.append(f"{field_path} (expected dict, got {type(output_value).__name__})")

        elif isinstance(expected_value, list):
            # Compare lists
            if isinstance(output_value, list):
                if len(expected_value) == 0:
                    field_scores[field_path] = 1.0
                    present_fields += 1
                else:
                    # Score based on overlap for string lists
                    if all(isinstance(x, str) for x in expected_value):
                        expected_set = set(str(x).lower() for x in expected_value)
                        output_set = set(str(x).lower() for x in output_value)
                        overlap = len(expected_set & output_set)
                        list_score = overlap / len(expected_set) if expected_set else 1.0
                        field_scores[field_path] = list_score
                        present_fields += list_score
                        if list_score < 1.0:
                            missing = expected_set - output_set
                            for item in missing:
                                missing_fields.append(f"{field_path}[]: {item}")
                    elif all(isinstance(x, dict) for x in expected_value):
                        # List of dicts - compare by index or length
                        if len(output_value) >= len(expected_value):
                            field_scores[field_path] = 1.0
                            present_fields += 1
                        else:
                            list_score = len(output_value) / len(expected_value)
                            field_scores[field_path] = list_score
                            present_fields += list_score
                            missing_fields.append(f"{field_path}: expected {len(expected_value)} items, got {len(output_value)}")
                    else:
                        field_scores[field_path] = 1.0 if len(output_value) > 0 else 0.0
                        present_fields += field_scores[field_path]
            else:
                field_scores[field_path] = 0.0
                missing_fields.append(f"{field_path} (expected list)")

        elif isinstance(expected_value, (str, int, float, bool)):
            # Simple value - check if present and non-empty
            if output_value is not None and str(output_value).strip():
                field_scores[field_path] = 1.0
                present_fields += 1
            else:
                field_scores[field_path] = 0.0
                missing_fields.append(field_path)
        else:
            # Unknown type - just check presence
            if output_value is not None:
                field_scores[field_path] = 1.0
                present_fields += 1
            else:
                field_scores[field_path] = 0.0
                missing_fields.append(field_path)

    overall_score = present_fields / total_fields if total_fields > 0 else 1.0
    return overall_score, field_scores, missing_fields


def evaluate_extraction(
    output: dict,
    expected: dict,
    sample_id: str,
    model: str,
    prompt_version: str,
    latency_ms: float,
) -> ExtractionResult:
    """Evaluate an extraction result against expected output.

    Args:
        output: The actual LLM extraction output
        expected: The expected/ground truth output
        sample_id: ID of the sample being tested
        model: Model name used
        prompt_version: Version of the prompt used
        latency_ms: Time taken in milliseconds

    Returns:
        ExtractionResult with computed metrics
    """
    score, field_scores, missing_fields = compute_completeness(output, expected)

    # Find extra fields not in expected
    extra_fields = []
    def find_extra(out: dict, exp: dict, path: str = ""):
        for key in out:
            field_path = f"{path}.{key}" if path else key
            if key not in exp:
                extra_fields.append(field_path)
            elif isinstance(out[key], dict) and isinstance(exp.get(key), dict):
                find_extra(out[key], exp[key], field_path)

    find_extra(output, expected)

    return ExtractionResult(
        sample_id=sample_id,
        model=model,
        prompt_version=prompt_version,
        output=output,
        expected=expected,
        latency_ms=latency_ms,
        completeness_score=score,
        field_scores=field_scores,
        missing_fields=missing_fields,
        extra_fields=extra_fields,
    )


def print_result_summary(result: ExtractionResult):
    """Print a human-readable summary of an extraction result."""
    status = "✓ PASS" if result.completeness_score >= 0.95 else "✗ FAIL"

    print(f"\n{'='*60}")
    print(f"Sample: {result.sample_id} | Model: {result.model}")
    print(f"Prompt: {result.prompt_version}")
    print(f"{'='*60}")
    print(f"Completeness: {result.completeness_score*100:.1f}% {status}")
    print(f"Latency: {result.latency_ms:.0f}ms")

    if result.missing_fields:
        print(f"\nMissing fields ({len(result.missing_fields)}):")
        for field in result.missing_fields[:10]:  # Limit to 10
            print(f"  - {field}")
        if len(result.missing_fields) > 10:
            print(f"  ... and {len(result.missing_fields) - 10} more")

    if result.extra_fields:
        print(f"\nExtra fields ({len(result.extra_fields)}):")
        for field in result.extra_fields[:5]:
            print(f"  + {field}")

    print()


@dataclass
class BenchmarkSummary:
    """Summary statistics for a benchmark run."""
    total_samples: int
    passed_samples: int
    avg_completeness: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    pass_rate: float
    model: str
    prompt_version: str
    results: list[ExtractionResult]

    @classmethod
    def from_results(cls, results: list[ExtractionResult]) -> "BenchmarkSummary":
        """Create summary from list of results."""
        if not results:
            raise ValueError("No results to summarize")

        total = len(results)
        passed = sum(1 for r in results if r.completeness_score >= 0.95)
        avg_comp = sum(r.completeness_score for r in results) / total
        latencies = [r.latency_ms for r in results]

        return cls(
            total_samples=total,
            passed_samples=passed,
            avg_completeness=avg_comp,
            avg_latency_ms=sum(latencies) / total,
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            pass_rate=passed / total,
            model=results[0].model,
            prompt_version=results[0].prompt_version,
            results=results,
        )

    def print_summary(self):
        """Print human-readable summary."""
        print(f"\n{'='*60}")
        print(f"BENCHMARK SUMMARY: {self.model} / {self.prompt_version}")
        print(f"{'='*60}")
        print(f"Samples: {self.passed_samples}/{self.total_samples} passed ({self.pass_rate*100:.1f}%)")
        print(f"Avg Completeness: {self.avg_completeness*100:.1f}%")
        print(f"Latency: {self.avg_latency_ms:.0f}ms avg ({self.min_latency_ms:.0f}-{self.max_latency_ms:.0f}ms)")

        # Show failing samples
        failing = [r for r in self.results if r.completeness_score < 0.95]
        if failing:
            print(f"\nFailing samples:")
            for r in failing:
                print(f"  - {r.sample_id}: {r.completeness_score*100:.1f}%")

        print()
