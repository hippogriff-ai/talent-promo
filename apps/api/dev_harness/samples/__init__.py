"""Sample inputs and expected outputs for prompt tuning.

Each sample file contains:
- input: Raw text (what EXA returns or user pastes)
- expected: The structured output we want (ground truth)
- metadata: Source info, difficulty rating, edge cases

Naming convention:
- profile_*.json - LinkedIn profile samples
- job_*.json - Job posting samples
- gap_*.json - Gap analysis samples (profile + job → analysis)
"""

import json
from pathlib import Path
from typing import Any

SAMPLES_DIR = Path(__file__).parent


def load_sample(agent_type: str, sample_id: str) -> dict[str, Any]:
    """Load a sample by agent type and ID.

    Args:
        agent_type: 'profile', 'job', or 'gap'
        sample_id: Sample identifier (e.g., '001', 'faang_engineer')

    Returns:
        Dict with 'input', 'expected', 'metadata'
    """
    path = SAMPLES_DIR / f"{agent_type}_{sample_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Sample not found: {path}")

    with open(path) as f:
        return json.load(f)


def list_samples(agent_type: str) -> list[str]:
    """List all sample IDs for an agent type."""
    pattern = f"{agent_type}_*.json"
    files = SAMPLES_DIR.glob(pattern)
    return [f.stem.replace(f"{agent_type}_", "") for f in files]


def save_sample(agent_type: str, sample_id: str, data: dict[str, Any]):
    """Save a new sample."""
    path = SAMPLES_DIR / f"{agent_type}_{sample_id}.json"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
