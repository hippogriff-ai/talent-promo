# Evals - Resume Agent Evaluation System

This folder contains evaluation tools for measuring and improving the quality of resume optimization outputs.

## Methodology

We use a **Silver Dataset + LLM-as-Judge** approach:

1. **Silver Datasets**: Curated test cases with expected behaviors (not gold-standard outputs)
2. **LLM Graders**: Use Claude to evaluate outputs against quality criteria
3. **Tuning Loops**: Iteratively improve prompts until target scores are achieved

## Directory Structure

```
evals/
├── datasets/           # Silver datasets for evaluation
├── graders/            # Scoring logic (rule-based and LLM-based)
├── results/            # Eval run outputs (gitignored)
├── run_eval.py         # One-off evaluation runner
├── *_tuning_loop.py    # Iterative prompt improvement loops
└── run_*_tuning.py     # CLI runners for tuning loops
```

## Datasets

### `datasets/drafting_samples.json`
**Purpose**: Evaluate draft quality and content highlighting
**Used by**: `drafting_tuning_loop.py`
**Contains**: 5 detailed profiles with job postings
**Evaluates**:
- Are the right skills/experiences highlighted?
- Are metrics quantified properly?
- Does draft meet minimum quality score?

### `datasets/drafting_examples.json`
**Purpose**: Evaluate user preference adherence
**Used by**: `run_eval.py`
**Contains**: 3 profiles with explicit user preferences
**Evaluates**:
- Tone (formal vs conversational)
- Structure (bullets vs paragraphs)
- First person usage
- Quantification level

### `datasets/discovery_samples.json`
**Purpose**: Evaluate discovery question quality
**Used by**: `discovery_tuning_loop.py`
**Contains**: Profiles with gap analysis + expected question qualities
**Evaluates**:
- Are questions specific (not generic)?
- Do they probe for hidden experiences?
- Do they avoid anti-patterns?

### `datasets/memory_samples.json`
**Purpose**: Evaluate preference learning from user edits
**Used by**: `memory_tuning_loop.py`
**Contains**: Sequences of user edit events
**Evaluates**:
- Can system infer first_person preference from edits?
- Can system detect tone preferences?

## Graders

### `graders/drafting_grader.py`
**Type**: Rule-based
**Evaluates**: Preference adherence, content quality, ATS compatibility
**Scores**: 0-1 on each dimension + weighted overall

### `graders/drafting_llm_grader.py`
**Type**: LLM-as-Judge (Claude)
**Evaluates**: Job relevance, achievement quality, professional quality, ATS optimization
**Scores**: 0-100 on each dimension
**Used in**: Tuning loops for iterative improvement

### `graders/discovery_grader.py`
**Type**: LLM-as-Judge (Claude)
**Evaluates**: Question specificity, probing quality, anti-pattern avoidance

### `graders/memory_grader.py`
**Type**: Rule-based comparison
**Evaluates**: Accuracy of inferred preferences vs expected preferences

## Scripts

### `run_eval.py`
One-off evaluation runner for quick testing.

```bash
# Run drafting eval
python -m evals.run_eval --stage drafting

# Upload results to LangSmith
python -m evals.run_eval --stage drafting --upload
```

### `run_drafting_tuning.py`
Iterative prompt tuning for drafting stage.

```bash
# Check current scores
python -m evals.run_drafting_tuning --check

# Run one improvement iteration
python -m evals.run_drafting_tuning --iterate

# View loop status
python -m evals.run_drafting_tuning --status
```

### `run_discovery_tuning.py`
Iterative prompt tuning for discovery questions.

```bash
python -m evals.run_discovery_tuning --check
python -m evals.run_discovery_tuning --iterate
```

## Tuning Loop Workflow

The tuning loops follow this pattern:

1. **Baseline**: Run eval on current prompts, record baseline score
2. **Iterate**: Make prompt changes, re-run eval, compare to baseline
3. **Target**: Continue until achieving 15% improvement over baseline
4. **Max iterations**: Stop after 10 iterations if target not met

State is persisted in `.*_tuning_state.json` files.

## Adding New Evals

1. Create dataset in `datasets/` with test cases
2. Create grader in `graders/` (rule-based or LLM)
3. Add tuning loop if iterative improvement is needed
4. Add CLI runner script

## LangSmith Integration

Results can be uploaded to LangSmith for tracking:
- Set `LANGSMITH_API_KEY` in `.env`
- Use `--upload` flag with `run_eval.py`
