"""
Decisions log writer for Nelson workflow.

This module provides utilities for appending structured decision entries to the decisions.md
file that tracks Nelson's autonomous decision-making process.

Also provides context compaction utilities for writing condensed progress summaries
that help maintain context efficiency during long-running tasks.
"""

from pathlib import Path
from typing import TextIO

from nelson.phases import Phase


class DecisionsLog:
    """Writer for Nelson's decisions log file (decisions.md)."""

    def __init__(self, log_path: Path) -> None:
        """
        Initialize decisions log writer.

        Args:
            log_path: Path to decisions.md file
        """
        self.log_path = log_path

    def append_decision(
        self,
        iteration: int,
        phase: int,
        phase_name: str,
        task: str,
        what_i_did: str,
        why: str,
        result: str,
    ) -> None:
        """
        Append a decision entry to the log.

        Args:
            iteration: Iteration number
            phase: Phase number (1-6)
            phase_name: Human-readable phase name (e.g., "Implementation")
            task: Task description from plan.md
            what_i_did: What was done (bullet points preferred)
            why: Why this approach was chosen
            result: Outcome of the task
        """
        entry = self._format_decision(iteration, phase, phase_name, task, what_i_did, why, result)
        self._append_to_file(entry)

    def append_phase_transition(self, iteration: int, from_phase: int, to_phase: int) -> None:
        """
        Append a phase transition entry to the log.

        Args:
            iteration: Iteration number
            from_phase: Phase number transitioning from
            to_phase: Phase number transitioning to
        """
        entry = self._format_phase_transition(iteration, from_phase, to_phase)
        self._append_to_file(entry)

    def append_summary(self, summary: str) -> None:
        """
        Append a summary section to the log.

        Args:
            summary: Summary text
        """
        entry = f"\n## Summary\n\n{summary}\n\n"
        self._append_to_file(entry)

    def _format_decision(
        self,
        iteration: int,
        phase: int,
        phase_name: str,
        task: str,
        what_i_did: str,
        why: str,
        result: str,
    ) -> str:
        """
        Format a decision entry.

        Args:
            iteration: Iteration number
            phase: Phase number
            phase_name: Human-readable phase name
            task: Task description
            what_i_did: Actions taken
            why: Rationale
            result: Outcome

        Returns:
            Formatted decision entry
        """
        # Ensure what_i_did has bullet points if it doesn't already
        if what_i_did and not what_i_did.strip().startswith("-"):
            what_i_did_lines = what_i_did.strip().split("\n")
            what_i_did = "\n".join(f"- {line}" for line in what_i_did_lines if line.strip())

        return f"""## [Iteration {iteration}] Phase {phase}: {phase_name}

**Task:** {task}

**What I Did:**
{what_i_did}

**Why:** {why}

**Result:** {result}

---
"""

    def _format_phase_transition(self, iteration: int, from_phase: int, to_phase: int) -> str:
        """
        Format a phase transition entry.

        Args:
            iteration: Iteration number
            from_phase: Phase transitioning from
            to_phase: Phase transitioning to

        Returns:
            Formatted phase transition entry
        """
        return f"""## Phase Transition (Iteration {iteration})

**From**: Phase {from_phase}
**To**: Phase {to_phase}

"""

    def _append_to_file(self, entry: str) -> None:
        """
        Append an entry to the decisions log file.

        Args:
            entry: Formatted entry to append
        """
        # Create parent directory if it doesn't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append entry to file
        with open(self.log_path, "a", encoding="utf-8") as f:
            # If file is empty or new, add header
            if self._is_empty_or_new():
                self._write_header(f)
            f.write(entry)

    def _is_empty_or_new(self) -> bool:
        """
        Check if log file is empty or doesn't exist.

        Returns:
            True if file is empty or doesn't exist
        """
        if not self.log_path.exists():
            return True
        return self.log_path.stat().st_size == 0

    def _write_header(self, f: TextIO) -> None:
        """
        Write the decisions log header.

        Args:
            f: File handle to write to
        """
        f.write("# Nelson Decisions Log\n\n")


def append_decision(
    log_path: Path,
    iteration: int,
    phase: int,
    phase_name: str,
    task: str,
    what_i_did: str,
    why: str,
    result: str,
) -> None:
    """
    Convenience function to append a decision entry.

    Args:
        log_path: Path to decisions.md file
        iteration: Iteration number
        phase: Phase number (1-6)
        phase_name: Human-readable phase name
        task: Task description
        what_i_did: Actions taken
        why: Rationale
        result: Outcome
    """
    log = DecisionsLog(log_path)
    log.append_decision(iteration, phase, phase_name, task, what_i_did, why, result)


def append_phase_transition(log_path: Path, iteration: int, from_phase: int, to_phase: int) -> None:
    """
    Convenience function to append a phase transition entry.

    Args:
        log_path: Path to decisions.md file
        iteration: Iteration number
        from_phase: Phase transitioning from
        to_phase: Phase transitioning to
    """
    log = DecisionsLog(log_path)
    log.append_phase_transition(iteration, from_phase, to_phase)


def append_summary(log_path: Path, summary: str) -> None:
    """
    Convenience function to append a summary section.

    Args:
        log_path: Path to decisions.md file
        summary: Summary text
    """
    log = DecisionsLog(log_path)
    log.append_summary(summary)


def write_progress_checkpoint(
    log_path: Path,
    original_task: str,
    current_phase: Phase,
    cycle: int,
    iteration: int,
    tasks_completed: int,
    tasks_remaining: int,
    current_state: str,
    approach: str,
    recent_work: list[str] | None = None,
    blockers: list[str] | None = None,
) -> None:
    """
    Write a condensed progress checkpoint for context compaction.

    This creates a summary that can be used to restore context efficiently
    after compaction or when resuming work. Unlike detailed decision logs,
    this provides a condensed snapshot of current state.

    Args:
        log_path: Path to decisions.md file
        original_task: The original user task
        current_phase: Current workflow phase
        cycle: Current cycle number
        iteration: Total iteration count
        tasks_completed: Number of tasks completed
        tasks_remaining: Number of tasks remaining
        current_state: Brief description of current state (1-2 sentences)
        approach: The approach being taken (1-2 sentences)
        recent_work: Optional list of recent completed work items
        blockers: Optional list of current blockers or issues
    """
    recent_work = recent_work or []
    blockers = blockers or []

    checkpoint = f"""
## ═══ PROGRESS CHECKPOINT (Iteration {iteration}) ═══

**Goal:** {original_task}

**Current Position:**
- Phase: {current_phase.value} ({current_phase.name})
- Cycle: {cycle}
- Progress: {tasks_completed} done, {tasks_remaining} remaining

**Approach:** {approach}

**Current State:** {current_state}
"""

    if recent_work:
        checkpoint += "\n**Recent Work:**\n"
        for item in recent_work[-5:]:  # Last 5 items max
            checkpoint += f"- {item}\n"

    if blockers:
        checkpoint += "\n**Current Issues:**\n"
        for blocker in blockers:
            checkpoint += f"- {blocker}\n"

    checkpoint += "\n═══════════════════════════════════════════════════════════════\n"

    log = DecisionsLog(log_path)
    log._append_to_file(checkpoint)


def should_compact(iteration: int, compact_interval: int = 10) -> bool:
    """
    Determine if context compaction should occur.

    Args:
        iteration: Current iteration number
        compact_interval: Number of iterations between compactions

    Returns:
        True if compaction should occur
    """
    return iteration > 0 and iteration % compact_interval == 0


def extract_recent_work(decisions_path: Path, max_items: int = 5) -> list[str]:
    """
    Extract recent work items from decisions log for checkpoint summary.

    Args:
        decisions_path: Path to decisions.md
        max_items: Maximum number of items to extract

    Returns:
        List of recent work descriptions
    """
    if not decisions_path.exists():
        return []

    content = decisions_path.read_text()
    work_items: list[str] = []

    # Extract from "What I Did" sections
    lines = content.splitlines()
    in_what_i_did = False

    for line in lines:
        if "**What I Did:**" in line:
            in_what_i_did = True
            continue
        elif line.startswith("**") and in_what_i_did:
            in_what_i_did = False
        elif in_what_i_did and line.strip().startswith("-"):
            item = line.strip().lstrip("- ").strip()
            if item and len(item) > 5:  # Skip very short items
                work_items.append(item)

    # Return most recent items
    return work_items[-max_items:] if work_items else []


def get_checkpoint_summary(decisions_path: Path) -> str | None:
    """
    Get the most recent checkpoint summary from decisions log.

    Useful for restoring context after compaction.

    Args:
        decisions_path: Path to decisions.md

    Returns:
        Most recent checkpoint text, or None if no checkpoint exists
    """
    if not decisions_path.exists():
        return None

    content = decisions_path.read_text()

    # Find the last checkpoint
    checkpoint_marker = "## ═══ PROGRESS CHECKPOINT"
    last_checkpoint_start = content.rfind(checkpoint_marker)

    if last_checkpoint_start == -1:
        return None

    # Extract until end marker
    end_marker = "═══════════════════════════════════════════════════════════════"
    checkpoint_section = content[last_checkpoint_start:]
    end_pos = checkpoint_section.find(end_marker)

    if end_pos != -1:
        return checkpoint_section[: end_pos + len(end_marker)]

    return checkpoint_section


def extract_recent_work_summary(log_path: Path, max_items: int = 3) -> str:
    """Extract condensed summary of recent decisions.

    Instead of raw lines, extract just:
    - Iteration number
    - Phase
    - Task name
    - Result (success/failure/blocked)

    Args:
        log_path: Path to decisions.md
        max_items: Number of recent items to extract

    Returns:
        Condensed summary string (~50-100 tokens vs 200-500)
    """
    if not log_path.exists():
        return ""

    content = log_path.read_text()
    lines = content.splitlines()

    # Find decision headers (## [Iteration N] Phase X: Task)
    summaries = []
    current_header = None

    for line in lines:
        # Match decision headers
        if line.startswith("## [Iteration"):
            # Extract: [Iteration N] Phase X: Task
            header = line.replace("##", "").strip()
            current_header = header

        # Extract result line
        elif line.startswith("**Result:**") and current_header:
            result = line.replace("**Result:**", "").strip()
            # Condense to single line
            summary = f"{current_header} - {result[:50]}"
            summaries.append(summary)
            current_header = None

    # Return last N summaries
    if summaries:
        return "\n".join(summaries[-max_items:])

    return ""
