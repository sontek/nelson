"""User interaction system for Nelson.

This module provides the infrastructure for strategic user interaction points:
- Planning phase questions
- Blocked state resolution
- Ambiguity clarification

Supports three modes:
- autonomous: Never prompt, use defaults immediately
- interactive: Prompt with timeouts, use defaults on timeout
- supervised: Prompt without timeouts, wait for user input
"""

from __future__ import annotations

import select
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    pass

console = Console()


def alert_user(
    title: str, message: str, enable_notifications: bool = True, enable_sound: bool = True
) -> None:
    """Alert user with terminal bell and/or desktop notification.

    Args:
        title: Notification title
        message: Notification message
        enable_notifications: Whether to send desktop notification
        enable_sound: Whether to play terminal bell

    Note:
        Desktop notifications fail gracefully if unavailable.
        Terminal bell works on all platforms.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Terminal bell (ASCII 07) - works everywhere
    if enable_sound:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception as e:
            logger.debug(f"Terminal bell failed: {e}")

    # Desktop notification (cross-platform via notify-py)
    if enable_notifications:
        try:
            from notifypy import Notify

            notification = Notify()
            notification.title = title
            notification.message = message
            notification.application_name = "Nelson"
            notification.send()
        except ImportError:
            logger.debug("notify-py not available, skipping desktop notification")
        except Exception as e:
            logger.debug(f"Desktop notification failed: {e}")


class InteractionMode(Enum):
    """User interaction mode."""

    AUTONOMOUS = "autonomous"  # Never prompt, use defaults
    INTERACTIVE = "interactive"  # Prompt with timeouts
    SUPERVISED = "supervised"  # Prompt without timeouts


@dataclass(frozen=True)
class InteractionConfig:
    """Configuration for user interaction behavior.

    Attributes:
        mode: Interaction mode (autonomous/interactive/supervised)
        planning_timeout_seconds: Timeout for planning questions (default: 60)
        ambiguity_timeout_seconds: Timeout for mid-execution questions (default: 30)
        prompt_on_blocked: Whether to prompt when tasks are blocked (default: True)
        skip_planning_questions: Skip planning questions entirely (default: False)
        enable_notifications: Enable desktop notifications when input needed (default: True)
        enable_sound_alert: Enable terminal bell sound when input needed (default: True)
    """

    mode: InteractionMode = InteractionMode.INTERACTIVE
    planning_timeout_seconds: int = 60
    ambiguity_timeout_seconds: int = 120
    prompt_on_blocked: bool = True
    skip_planning_questions: bool = False
    enable_notifications: bool = True
    enable_sound_alert: bool = True

    @classmethod
    def from_env(cls) -> InteractionConfig:
        """Create InteractionConfig from environment variables.

        Environment variables:
            NELSON_INTERACTION_MODE: autonomous|interactive|supervised
            NELSON_PLANNING_TIMEOUT: Seconds for planning questions
            NELSON_AMBIGUITY_TIMEOUT: Seconds for ambiguity questions
            NELSON_PROMPT_ON_BLOCKED: true|false
            NELSON_SKIP_PLANNING_QUESTIONS: true|false
            NELSON_ENABLE_NOTIFICATIONS: true|false
            NELSON_ENABLE_SOUND_ALERT: true|false

        Returns:
            InteractionConfig with values from environment
        """
        import os

        mode_str = os.environ.get("NELSON_INTERACTION_MODE", "interactive").lower()
        try:
            mode = InteractionMode(mode_str)
        except ValueError:
            mode = InteractionMode.INTERACTIVE

        planning_timeout = int(os.environ.get("NELSON_PLANNING_TIMEOUT", "60"))
        ambiguity_timeout = int(os.environ.get("NELSON_AMBIGUITY_TIMEOUT", "120"))
        prompt_on_blocked = os.environ.get("NELSON_PROMPT_ON_BLOCKED", "true").lower() == "true"
        skip_planning = os.environ.get("NELSON_SKIP_PLANNING_QUESTIONS", "false").lower() == "true"
        enable_notifications = (
            os.environ.get("NELSON_ENABLE_NOTIFICATIONS", "true").lower() == "true"
        )
        enable_sound_alert = os.environ.get("NELSON_ENABLE_SOUND_ALERT", "true").lower() == "true"

        return cls(
            mode=mode,
            planning_timeout_seconds=planning_timeout,
            ambiguity_timeout_seconds=ambiguity_timeout,
            prompt_on_blocked=prompt_on_blocked,
            skip_planning_questions=skip_planning,
            enable_notifications=enable_notifications,
            enable_sound_alert=enable_sound_alert,
        )


@dataclass
class Question:
    """A question to ask the user.

    Attributes:
        id: Unique identifier for the question
        question: The question text
        options: List of options (None for free text)
        default: Default answer if timeout or autonomous mode
        context: Explanation of why this question matters
        timeout_seconds: Override timeout for this specific question
    """

    id: str
    question: str
    options: list[str] | None
    default: str
    context: str = ""
    timeout_seconds: int | None = None


@dataclass
class Answer:
    """An answer from the user.

    Attributes:
        question_id: ID of the question being answered
        response: The user's response
        was_timeout: Whether the answer was from a timeout
        was_default: Whether the default was used (timeout or autonomous)
        timestamp: When the answer was recorded
    """

    question_id: str
    response: str
    was_timeout: bool = False
    was_default: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class UserInteraction:
    """Handles user interaction with timeout support.

    This class manages prompting users for input with configurable
    timeouts and modes. In autonomous mode, it returns defaults
    immediately. In interactive mode, it waits for input with a
    countdown timer. In supervised mode, it waits indefinitely.
    """

    def __init__(self, config: InteractionConfig) -> None:
        """Initialize UserInteraction.

        Args:
            config: Interaction configuration
        """
        self.config = config
        self.console = Console()

    def ask_question(self, question: Question) -> Answer:
        """Ask a question and get an answer.

        In autonomous mode, immediately returns the default.
        In interactive mode, shows the question with a countdown.
        In supervised mode, waits indefinitely for input.

        Args:
            question: The question to ask

        Returns:
            Answer with the user's response or default
        """
        # Autonomous mode: return default immediately
        if self.config.mode == InteractionMode.AUTONOMOUS:
            return Answer(
                question_id=question.id,
                response=question.default,
                was_timeout=False,
                was_default=True,
            )

        # Determine timeout
        timeout = question.timeout_seconds
        if timeout is None:
            timeout = self.config.planning_timeout_seconds

        # Supervised mode: no timeout
        if self.config.mode == InteractionMode.SUPERVISED:
            timeout = None

        # Display the question
        self._display_question(question, timeout)

        # Get input with timeout
        response = self._get_input_with_timeout(timeout, question.default)

        if response is None:
            # Timeout occurred
            return Answer(
                question_id=question.id,
                response=question.default,
                was_timeout=True,
                was_default=True,
            )

        # Parse response if options provided
        if question.options:
            response = self._parse_option_response(response, question.options, question.default)

        return Answer(
            question_id=question.id,
            response=response,
            was_timeout=False,
            was_default=False,
        )

    def ask_multiple_choice(
        self,
        question: str,
        options: list[str],
        default_index: int = 0,
        context: str = "",
        timeout_seconds: int | None = None,
    ) -> tuple[str, bool]:
        """Ask a multiple choice question.

        Convenience method for simple multiple choice questions.

        Args:
            question: The question text
            options: List of options to choose from
            default_index: Index of default option (0-based)
            context: Optional context explaining the question
            timeout_seconds: Override default timeout

        Returns:
            Tuple of (selected_option, was_default)
        """
        q = Question(
            id=f"mc_{hash(question) % 10000}",
            question=question,
            options=options,
            default=options[default_index] if options else "",
            context=context,
            timeout_seconds=timeout_seconds,
        )
        answer = self.ask_question(q)
        return answer.response, answer.was_default

    def ask_yes_no(
        self,
        question: str,
        default: bool = True,
        context: str = "",
        timeout_seconds: int | None = None,
    ) -> tuple[bool, bool]:
        """Ask a yes/no question.

        Args:
            question: The question text
            default: Default answer (True=yes, False=no)
            context: Optional context explaining the question
            timeout_seconds: Override default timeout

        Returns:
            Tuple of (answer_bool, was_default)
        """
        options = ["Yes", "No"]
        default_str = "Yes" if default else "No"

        q = Question(
            id=f"yn_{hash(question) % 10000}",
            question=question,
            options=options,
            default=default_str,
            context=context,
            timeout_seconds=timeout_seconds,
        )
        answer = self.ask_question(q)
        return answer.response.lower() in ("yes", "y", "1"), answer.was_default

    def ask_free_text(
        self,
        question: str,
        default: str = "",
        context: str = "",
        timeout_seconds: int | None = None,
    ) -> tuple[str, bool]:
        """Ask a free text question.

        Args:
            question: The question text
            default: Default answer
            context: Optional context explaining the question
            timeout_seconds: Override default timeout

        Returns:
            Tuple of (response_text, was_default)
        """
        q = Question(
            id=f"ft_{hash(question) % 10000}",
            question=question,
            options=None,  # Free text
            default=default,
            context=context,
            timeout_seconds=timeout_seconds,
        )
        answer = self.ask_question(q)
        return answer.response, answer.was_default

    def _display_question(self, question: Question, timeout: int | None) -> None:
        """Display a question with options and timeout info.

        Args:
            question: The question to display
            timeout: Timeout in seconds (None for no timeout)
        """
        # Alert user before displaying question
        alert_user(
            title="Nelson Needs Input",
            message=question.question[:100],  # Truncate long questions
            enable_notifications=self.config.enable_notifications,
            enable_sound=self.config.enable_sound_alert,
        )

        # Build question content
        content_parts = [f"\n{question.question}\n"]

        if question.context:
            content_parts.append(f"\n[dim]{question.context}[/dim]\n")

        if question.options:
            content_parts.append("")
            for i, option in enumerate(question.options, 1):
                marker = "(Recommended)" if option == question.default else ""
                content_parts.append(f"  [{i}] {option} {marker}")
            content_parts.append("")

        if timeout:
            timeout_msg = f"\n[dim]⏱ Using default [{question.default}] in {timeout}s...[/dim]"
            content_parts.append(timeout_msg)

        content = "\n".join(content_parts)

        # Display panel
        self.console.print(
            Panel(
                content,
                title="[bold cyan]Nelson needs input[/bold cyan]",
                border_style="cyan",
                padding=(0, 2),
            )
        )

    def _get_input_with_timeout(self, timeout: int | None, default: str) -> str | None:
        """Get user input with optional timeout.

        Args:
            timeout: Timeout in seconds (None for no timeout)
            default: Default value to show in countdown

        Returns:
            User input string, or None if timeout occurred
        """
        if timeout is None:
            # No timeout - just get input
            try:
                return input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

        # Check if stdin is a TTY (interactive terminal)
        if not sys.stdin.isatty():
            # Non-interactive: return default immediately
            self.console.print(f"[dim]Non-interactive mode, using default: {default}[/dim]")
            return None

        # Use select for timeout on Unix systems
        try:
            # Use raw stdout instead of rich console to avoid interference
            sys.stdout.write("> ")
            sys.stdout.flush()

            remaining = timeout

            while remaining > 0:
                # Check if input is available
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)

                if ready:
                    # Input available
                    line = sys.stdin.readline()
                    if line:
                        # Clear any countdown message that might be on the line
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return line.strip()
                    return None  # EOF

                remaining -= 1

                # Show countdown every 10 seconds
                if remaining > 0 and remaining % 10 == 0:
                    # Use raw stdout to avoid rich console interference
                    countdown_msg = f"\r⏱ {remaining}s remaining, using [{default}]..."
                    sys.stdout.write(countdown_msg)
                    sys.stdout.flush()

            # Timeout
            sys.stdout.write("\n")
            sys.stdout.flush()
            self.console.print(f"[yellow]Timeout - using default: {default}[/yellow]")
            return None

        except (OSError, ValueError):
            # select not supported (Windows without proper terminal)
            # Fall back to simple input with no timeout
            self.console.print(
                f"[dim]Timeout not supported, waiting for input (default: {default})...[/dim]"
            )
            try:
                return input().strip()
            except (EOFError, KeyboardInterrupt):
                return None

    def _parse_option_response(self, response: str, options: list[str], default: str) -> str:
        """Parse user response to option selection.

        Handles:
        - Numeric selection (1, 2, 3)
        - Text matching (partial or full option text)
        - Empty input (use default)

        Args:
            response: User's raw response
            options: Available options
            default: Default option

        Returns:
            Selected option string
        """
        if not response:
            return default

        # Try numeric selection
        try:
            idx = int(response) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass

        # Try text matching (case-insensitive)
        response_lower = response.lower()
        for option in options:
            if option.lower() == response_lower:
                return option
            if option.lower().startswith(response_lower):
                return option

        # No match - return default
        return default


def log_interaction(
    question: Question,
    answer: Answer,
    decisions_file: Path,
) -> None:
    """Log an interaction to the decisions file.

    Args:
        question: The question that was asked
        answer: The answer received
        decisions_file: Path to decisions.md
    """
    # Build log entry
    lines = [
        "",
        "## User Interaction",
        "",
        f"**Question**: {question.question}",
    ]

    if question.options:
        lines.append(f"**Options**: {', '.join(question.options)}")

    lines.append(f"**Answer**: {answer.response}")

    if answer.was_timeout:
        lines.append("**Note**: Timeout - used default")
    elif answer.was_default:
        lines.append("**Note**: Autonomous mode - used default")

    lines.append(f"**Timestamp**: {answer.timestamp.isoformat()}")
    lines.append("")

    # Append to file
    with open(decisions_file, "a") as f:
        f.write("\n".join(lines))
