"""Depth mode configuration for Nelson.

This module provides depth modes that control task complexity handling:
- QUICK: 4 phases, lean prompts, for simple fixes and typos
- STANDARD: 5 phases, full prompts, for normal features and bug fixes
- COMPREHENSIVE: 7 phases with discover and roadmap, for large projects
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DepthMode(Enum):
    """Depth mode controlling task complexity handling."""

    QUICK = "quick"  # 4 phases, lean prompts
    STANDARD = "standard"  # 5 phases, full prompts
    COMPREHENSIVE = "comprehensive"  # 7 phases with discover and roadmap


# Default configurations per depth mode
_DEPTH_DEFAULTS: dict[DepthMode, dict[str, Any]] = {
    DepthMode.QUICK: {
        "skip_review": True,  # Skip review phase in quick mode
        "skip_roadmap": True,
        "include_research": False,
        "max_planning_questions": 0,
        "lean_prompts": True,
    },
    DepthMode.STANDARD: {
        "skip_review": False,
        "skip_roadmap": True,
        "include_research": False,
        "max_planning_questions": 3,
        "lean_prompts": False,
    },
    DepthMode.COMPREHENSIVE: {
        "skip_review": False,
        "skip_roadmap": False,
        "include_research": True,
        "max_planning_questions": 5,
        "lean_prompts": False,
    },
}


@dataclass(frozen=True)
class DepthConfig:
    """Configuration for depth mode behavior.

    Attributes:
        mode: The depth mode (QUICK, STANDARD, COMPREHENSIVE)
        skip_review: Skip REVIEW phase (Phase 4) - used in QUICK mode
        skip_roadmap: Skip roadmap creation for complex tasks
        include_research: Include research/discovery phase
        max_planning_questions: Maximum clarifying questions to ask
        lean_prompts: Use lean prompts instead of detailed
    """

    mode: DepthMode
    skip_review: bool
    skip_roadmap: bool
    include_research: bool
    max_planning_questions: int
    lean_prompts: bool

    @classmethod
    def for_mode(cls, mode: DepthMode) -> DepthConfig:
        """Create DepthConfig with defaults for the given mode.

        Args:
            mode: Depth mode to configure

        Returns:
            DepthConfig with mode-appropriate defaults
        """
        defaults = _DEPTH_DEFAULTS[mode]
        return cls(
            mode=mode,
            skip_review=defaults["skip_review"],
            skip_roadmap=defaults["skip_roadmap"],
            include_research=defaults["include_research"],
            max_planning_questions=defaults["max_planning_questions"],
            lean_prompts=defaults["lean_prompts"],
        )

    @classmethod
    def from_env(cls) -> DepthConfig:
        """Create DepthConfig from environment variables.

        Environment variables:
            NELSON_DEPTH: quick|standard|comprehensive (default: standard)

        Returns:
            DepthConfig with values from environment
        """
        depth_str = os.environ.get("NELSON_DEPTH", "standard").lower()

        try:
            mode = DepthMode(depth_str)
        except ValueError:
            mode = DepthMode.STANDARD

        return cls.for_mode(mode)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode.value,
            "skip_review": self.skip_review,
            "skip_roadmap": self.skip_roadmap,
            "include_research": self.include_research,
            "max_planning_questions": self.max_planning_questions,
            "lean_prompts": self.lean_prompts,
        }


def get_phases_for_depth(depth: DepthConfig) -> list[str]:
    """Get the list of phases for a given depth configuration.

    Args:
        depth: Depth configuration

    Returns:
        List of phase names in execution order
    """
    if depth.mode == DepthMode.QUICK:
        # Quick mode: 4 phases, skip REVIEW
        return ["PLAN", "IMPLEMENT", "TEST", "COMMIT"]

    # STANDARD mode: 5 phases
    # COMPREHENSIVE mode: 7 phases (adds DISCOVER and ROADMAP)
    phases = ["PLAN", "IMPLEMENT", "TEST"]

    if not depth.skip_review:
        phases.append("REVIEW")

    phases.append("COMMIT")

    # COMPREHENSIVE adds DISCOVER at the beginning and ROADMAP at the end
    if depth.include_research:
        phases = ["DISCOVER"] + phases

    if not depth.skip_roadmap:
        phases.append("ROADMAP")

    return phases


def should_skip_phase(phase_name: str, depth: DepthConfig) -> bool:
    """Check if a phase should be skipped based on depth config.

    Args:
        phase_name: Name of the phase
        depth: Depth configuration

    Returns:
        True if phase should be skipped
    """
    if depth.mode == DepthMode.QUICK:
        # Quick mode skips REVIEW
        if phase_name == "REVIEW":
            return True

    if depth.skip_review and phase_name == "REVIEW":
        return True

    if depth.skip_roadmap and phase_name == "ROADMAP":
        return True

    if not depth.include_research and phase_name == "DISCOVER":
        return True

    return False
