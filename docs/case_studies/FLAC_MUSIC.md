# Case Study: Integrating ACE-Lite MCP in Android Kotlin Projects

## Context

This document outlines the practical experience and feedback from integrating the **ACE-Lite Engine (v0.3.25)** into `FLAC Music` - a complex, multi-layered Android music player built with Kotlin, Jetpack Compose, ExoPlayer, and Room.

## The Problem Before ACE-Lite

In a layered architecture (UI -> ViewModel -> Controller -> Service -> Player), standard LLM agents often struggle because:
1. They perform noisy, repository-wide searches that pull in irrelevant files.
2. They forget implied architectural constraints (e.g., "Don't instantiate ExoPlayer in the UI layer").
3. Changing a data model requires knowing exactly which repositories, ViewModels, and UI screens need updates.

## How ACE-Lite Solved It

### 1. Zero-Noise Targeted Retrieval (`ace_plan_quick`)
By configuring `plan_quick` with the `languages="java,kotlin"` scope and using the `rrf_hybrid` ranker, ACE-Lite consistently surfaced the correct target files within **~500ms**.
*Example: Querying `"player viewmodel playback service audio"` accurately ranked `MusicService.kt` and `PlayerViewModel.kt` at the very top, avoiding contamination from Python or shell scripts in the workspace.*

### 2. Dependency Awareness (`repomap_expand`)
Using `repomap_expand=true` with a `neighbor_depth=1` allowed the agent to look slightly beyond the initial hits. Before even opening a file, the agent understood exactly which ViewModels depended on the target Repository, acting as a powerful "blast radius" detector.

### 3. "Team Memory" via `ace_memory_store`
Instead of reminding the agent about the project's rules in every new session, we injected core architectural facts directly into ACE-Lite's memory:
```bash
ace-lite memory store "[flac_music] UI layer must communicate with ExoPlayer only via MusicConnection and PlayerViewModel." --namespace flac_music
```
With this setup, the engine autonomously loads these constraints during the `ace_health` and `ace_memory_search` pre-flight checks. The agent effectively behaves like a "senior engineer" who remembers the project's implicit rules.

### 4. Self-Optimizing Feedback Loops
The `ace_feedback_record` tool was integrated into the agent's workflow. Whenever the agent narrowed down the exact file to modify for a bugfix or feature, it recorded the pairing (Query + Selected File). Over time, the ranking system automatically learns to associate specific domain terms (like "theme switch") with their respective files (`Color.kt`, `Theme.kt`).

## Best Practices Adopted

We encapsulated this workflow into an agent-specific `SKILL.md` (named `ace-context-dev`), defining a strict 4-phase sequence:
1. **Pre-flight:** `ace_health` + `ace_memory_search` (Recover context)
2. **Targeting:** `ace_plan_quick` (Filter and rank candidates)
3. **Execution:** Modify code + `ace_feedback_record` (Learn for the future)
4. **Distillation:** `ace_memory_store` (Save new architectural discoveries)

To make it frictionless, a slash command (`/ace`) was created to launch this exact pipeline automatically.

## Conclusion

ACE-Lite proved to be extremely effective for medium-to-large structured projects. By preventing context pollution and injecting long-term architectural memory, it shifted the AI coding experience from "hunting for the right file" to "executing safe, context-aware changes".
