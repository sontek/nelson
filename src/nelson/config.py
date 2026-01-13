"""Configuration management for Nelson.

This module handles environment variables, defaults, and configuration validation.
All configuration is immutable after creation for predictability.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Valid model identifiers
ModelType = Literal["opus", "sonnet", "haiku"]


@dataclass(frozen=True)
class NelsonConfig:
    """Configuration for Nelson orchestration.

    All configuration is immutable (frozen dataclass) to ensure consistent behavior
    throughout a run. Configuration is loaded once at startup.
    """

    # Iteration and cost limits
    max_iterations: int  # Max complete 6-phase cycles (not total phase executions)
    max_iterations_explicit: bool  # True if user explicitly set max_iterations
    cost_limit: float

    # Directory paths
    nelson_dir: Path
    audit_dir: Path
    runs_dir: Path
    target_path: Path | None  # Optional target repository path (None = current directory)

    # Claude command configuration
    claude_command: str  # "claude", "claude-jail", or custom path
    claude_command_path: Path | None  # Resolved path to claude executable

    # Model selection
    model: str
    plan_model: str
    review_model: str

    # Git/Push configuration
    auto_approve_push: bool

    @classmethod
    def from_environment(
        cls, script_dir: Path | None = None, target_path: Path | None = None
    ) -> "NelsonConfig":
        """Load configuration from environment variables with defaults.

        Args:
            script_dir: Directory containing the nelson script (for claude-jail resolution).
                       If None, uses parent directory of this module.
            target_path: Optional target repository directory. If None, uses current directory.

        Returns:
            Immutable NelsonConfig instance.
        """
        # Detect if NELSON_MAX_ITERATIONS was explicitly set
        max_iterations_str = os.getenv("NELSON_MAX_ITERATIONS")
        max_iterations_explicit = max_iterations_str is not None
        max_iterations = int(max_iterations_str) if max_iterations_str else 10

        # Cost limit in USD
        cost_limit = float(os.getenv("NELSON_COST_LIMIT", "10.00"))

        # Directory configuration
        nelson_dir = Path(os.getenv("NELSON_DIR", ".nelson"))
        audit_dir = Path(os.getenv("NELSON_AUDIT_DIR", ".nelson/audit"))
        runs_dir = Path(os.getenv("NELSON_RUNS_DIR", ".nelson/runs"))

        # Claude command configuration
        claude_command = os.getenv("NELSON_CLAUDE_COMMAND", "claude-jail")

        # Model selection with cascading defaults
        model = os.getenv("NELSON_MODEL", "sonnet")
        plan_model = os.getenv("NELSON_PLAN_MODEL", model)
        review_model = os.getenv("NELSON_REVIEW_MODEL", model)

        # Git configuration
        auto_approve_push = os.getenv("NELSON_AUTO_APPROVE_PUSH", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        # Resolve claude command path
        claude_command_path = cls._resolve_claude_path(claude_command, script_dir)

        return cls(
            max_iterations=max_iterations,
            max_iterations_explicit=max_iterations_explicit,
            cost_limit=cost_limit,
            nelson_dir=nelson_dir,
            audit_dir=audit_dir,
            runs_dir=runs_dir,
            target_path=target_path,
            claude_command=claude_command,
            claude_command_path=claude_command_path,
            model=model,
            plan_model=plan_model,
            review_model=review_model,
            auto_approve_push=auto_approve_push,
        )

    @staticmethod
    def _resolve_claude_path(claude_command: str, script_dir: Path | None) -> Path | None:
        """Resolve the path to the claude executable.

        Args:
            claude_command: Command from configuration ("claude", "claude-jail", or path)
            script_dir: Directory containing nelson script (for claude-jail resolution)

        Returns:
            Resolved path to claude executable, or None if using system "claude" command
        """
        if claude_command == "claude":
            # Use system claude command (no explicit path)
            return None
        elif claude_command == "claude-jail":
            # Resolve claude-jail relative to script directory
            if script_dir is None:
                # Default to parent of this module's directory (bin/)
                script_dir = Path(__file__).parent.parent.parent / "bin"
            return script_dir / "claude-jail"
        else:
            # Custom path provided
            return Path(claude_command)

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid
        """
        if self.max_iterations <= 0:
            raise ValueError(f"max_iterations must be > 0, got {self.max_iterations}")

        if self.cost_limit <= 0:
            raise ValueError(f"cost_limit must be > 0, got {self.cost_limit}")

        if self.claude_command_path and not self.claude_command_path.exists():
            raise ValueError(f"Claude command path does not exist: {self.claude_command_path}")

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.nelson_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


# Constants for directory names
CLAUDE_DIR = Path(".claude")  # Claude Code's own directory
STATE_FILE_NAME = "state.json"
PLAN_FILE_NAME = "plan.md"
DECISIONS_FILE_NAME = "decisions.md"
AUDIT_FILE_NAME = "audit.log"
