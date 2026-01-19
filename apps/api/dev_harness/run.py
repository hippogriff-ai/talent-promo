#!/usr/bin/env python3
"""CLI for running prompt benchmarks.

Usage:
    # Run benchmark for profile extraction
    python -m dev_harness.run profile v1_original

    # Run with different model
    python -m dev_harness.run profile v1_original --model claude-3-5-sonnet-20241022

    # Compare two versions
    python -m dev_harness.run profile --compare v1_original v2_concise

    # Offline mode (no LLM calls, for testing)
    python -m dev_harness.run profile v1_original --offline

    # Use LLM as judge
    python -m dev_harness.run profile v1_original --llm-judge

    # Save report to file
    python -m dev_harness.run profile v1_original --save
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dev_harness.runners import (
    run_prompt_benchmark,
    compare_prompts,
    save_report,
    PROMPTS,
)
from dev_harness.samples import list_samples


def main():
    parser = argparse.ArgumentParser(
        description="Run prompt benchmarks for tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m dev_harness.run profile v1_original
  python -m dev_harness.run job v1_original --model claude-3-5-sonnet-20241022
  python -m dev_harness.run profile --compare v1_original v2_concise
  python -m dev_harness.run profile v1_original --offline --save
        """
    )

    parser.add_argument(
        "agent_type",
        choices=["profile", "job", "gap"],
        help="Type of extraction to benchmark"
    )

    parser.add_argument(
        "prompt_version",
        nargs="?",
        default=None,
        help="Prompt version to test (e.g., v1_original)"
    )

    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("VERSION_A", "VERSION_B"),
        help="Compare two prompt versions"
    )

    parser.add_argument(
        "--model",
        default="claude-3-haiku-20240307",
        help="Model to use (default: claude-3-haiku-20240307)"
    )

    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline (no LLM calls, uses expected as actual)"
    )

    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Use LLM as judge instead of structured comparison"
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to file"
    )

    parser.add_argument(
        "--list-samples",
        action="store_true",
        help="List available samples for agent type"
    )

    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="List available prompt versions"
    )

    args = parser.parse_args()

    # List samples
    if args.list_samples:
        samples = list_samples(args.agent_type)
        print(f"Samples for {args.agent_type}:")
        for s in samples:
            print(f"  - {s}")
        return

    # List prompts
    if args.list_prompts:
        extraction_type = f"{args.agent_type}_extraction"
        if extraction_type in PROMPTS:
            print(f"Prompt versions for {args.agent_type}:")
            for version in PROMPTS[extraction_type]:
                print(f"  - {version}")
        else:
            print(f"No prompts defined for {args.agent_type}")
        return

    # Compare two versions
    if args.compare:
        version_a, version_b = args.compare
        print(f"Comparing {version_a} vs {version_b}...")

        result = compare_prompts(
            args.agent_type,
            version_a,
            version_b,
            args.model,
        )

        print(f"\n{'='*60}")
        print(f"WINNER: {result['winner']}")
        print(f"{'='*60}")
        print(f"\n{version_a}:")
        print(f"  Score: {result['version_a']['avg_score']*100:.1f}%")
        print(f"  Latency: {result['version_a']['avg_latency_ms']:.0f}ms")
        print(f"  Pass: {result['version_a']['pass_count']}")

        print(f"\n{version_b}:")
        print(f"  Score: {result['version_b']['avg_score']*100:.1f}%")
        print(f"  Latency: {result['version_b']['avg_latency_ms']:.0f}ms")
        print(f"  Pass: {result['version_b']['pass_count']}")

        print(f"\nDelta: {result['score_delta']*100:+.1f}% score, {result['latency_delta_ms']:+.0f}ms latency")
        return

    # Run single benchmark
    if not args.prompt_version:
        parser.error("prompt_version is required unless using --compare, --list-samples, or --list-prompts")

    print(f"Running benchmark: {args.agent_type}/{args.prompt_version}")
    print(f"Model: {args.model}")
    print(f"Mode: {'offline' if args.offline else 'online'}")
    print()

    try:
        summary = run_prompt_benchmark(
            args.agent_type,
            args.prompt_version,
            args.model,
            use_llm_judge=args.llm_judge,
            offline=args.offline,
        )

        print(summary.summary())

        if args.save:
            path = save_report(summary)
            print(f"\nReport saved to: {path}")

        # Return exit code based on pass rate
        if summary.fail_count > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(f"\nAvailable samples: {list_samples(args.agent_type)}")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Unknown prompt version: {e}")
        extraction_type = f"{args.agent_type}_extraction"
        if extraction_type in PROMPTS:
            print(f"Available versions: {list(PROMPTS[extraction_type].keys())}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
