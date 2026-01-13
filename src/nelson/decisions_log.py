"""
Decisions log writer for Nelson workflow.

This module provides utilities for appending structured decision entries to the decisions.md
file that tracks Nelson's autonomous decision-making process.
"""

from pathlib import Path
from typing import TextIO


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
