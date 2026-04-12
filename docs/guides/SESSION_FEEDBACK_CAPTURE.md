# Session Feedback Capture Guide

This guide describes when and how to capture feedback during ACE-Lite sessions to improve future retrieval quality.

## Overview

The feedback system captures user selections to improve ranking over time. Proper feedback capture enables:

- Better ranking of frequently selected files
- Identification of gaps between shortlists and actual selections
- Measurement of retrieval system effectiveness

## When to Record Feedback

### 1. After User Opens a Shortlisted File

When a user opens a file that appeared in `ace_plan_quick` or `ace_plan` results:

```python
# Example: User clicked on file from plan_quick results
candidate_files = result["candidate_files"]  # From ace_plan_quick
selected_path = "src/auth/token.py"  # User opened this file

# Record feedback
feedback_record(
    query=original_query,
    selected_path=selected_path,
    candidate_paths=candidate_files,
    position=candidate_files.index(selected_path) + 1 if selected_path in candidate_files else None,
)
```

### 2. After Agent Cites a Selected File:Line

When the agent references a specific file and line number:

```python
# Example: Agent cited src/auth/token.py:42
# Keep citation context in your host-side session log if you need to distinguish
# it from click/open feedback. feedback_record() itself only accepts supported
# selection fields.
feedback_record(
    query=original_query,
    selected_path="src/auth/token.py",
    candidate_paths=candidate_files,
)
```

### 3. After Editing a File Chosen from Plan Results

When a user edits a file that was suggested by plan_quick/plan:

```python
# Example: User edited a file from the plan results
# Keep post-edit context in your host-side session log. feedback_record() stores
# the final selected path and shortlist, and derives internal capture metadata.
feedback_record(
    query=original_query,
    selected_path=edited_file_path,
    candidate_paths=candidate_files,
)
```

## Query Rewriting Feedback

When the query is rewritten based on system suggestions:

```python
# Original query and refined query
original_query = "explainability requirements"
refined_query = "docs planning explainability requirements"

# Record the refined query that actually produced the shortlist.
# If you also need the original query or refinement code, persist them in your
# host-side session log rather than sending unsupported fields to feedback_record().
feedback_record(
    query=refined_query,
    selected_path=selected_path,
    candidate_paths=new_candidate_files,
)
```

## Feedback Capture Template

```python
def capture_session_feedback(
    *,
    query: str,
    selected_path: str,
    candidate_paths: list[str],
    position: int | None = None,
    repo: str | None = None,
) -> dict:
    """Capture feedback from a session interaction.

    Args:
        query: The query that produced the candidate list
        selected_path: The file path the user ultimately selected
        candidate_paths: The list of candidate files presented
        position: 1-based position of selected_path in candidate_paths (if applicable)
        repo: Repository identifier

    Returns:
        Feedback record result
    """
    # Send to feedback store
    return feedback_record(
        query=query,
        selected_path=selected_path,
        candidate_paths=candidate_paths,
        position=position,
        repo=repo or "default",
    )
```

## Measuring Feedback Quality

Use `feedback_stats` to check if feedback is improving retrieval:

```python
stats = feedback_stats(repo="my-repo")

# Key metrics to monitor:
metrics = stats["decision_metrics"]
print(f"Attach rate: {metrics['final_selected_paths_attach_rate']}")
print(f"Shortlist precision: {metrics['shortlist_to_selection_precision']}")
print(f"Reuse lift: {metrics['feedback_reuse_lift']}")
```

### Interpreting Metrics

- **final_selected_paths_attach_rate**: Higher is better (1.0 = all selections were in candidates)
- **shortlist_to_selection_precision**: Higher is better (1.0 = selections always at position 1)
- **feedback_reuse_lift**: Higher is better (indicates repeat selections of same files)
- **selection_replay_precision_delta**: Positive = recent selections more precise than older ones

## Best Practices

1. **Capture Early and Often**: Record feedback for every significant selection
2. **Include Position**: Always include position when available for precision tracking
3. **Track Query Evolution**: Keep original and refined queries in host-side session logs for later correlation
4. **Track Capture Context Separately**: Keep citation, post-edit, or explicit-confirmation context in host-side logs unless the public API adds a dedicated field
5. **Monitor Metrics**: Regularly check decision_metrics to ensure feedback is helping

## Common Pitfalls

- **Over-capturing**: Don't record every file access, only meaningful selections
- **Missing Context**: Always include candidate_paths to calculate attach_rate
- **Ignoring Position**: Position data is crucial for precision metrics
- **Assuming Extra Fields Are Accepted**: Do not pass host-only fields such as `capture_mode` unless the public CLI/MCP contract explicitly supports them
- **Not Checking Metrics**: Feedback without measurement may not improve retrieval
