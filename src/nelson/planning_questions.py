"""Planning phase question handling.

This module provides infrastructure for Claude to ask clarifying questions
during the PLAN phase before committing to an implementation approach.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nelson.interaction import UserInteraction

logger = logging.getLogger(__name__)


class QuestionCategory(Enum):
    """Category of planning question for prioritization."""

    REQUIREMENTS = "requirements"  # Core functionality unclear
    ARCHITECTURE = "architecture"  # Multiple valid approaches
    SCOPE = "scope"  # Boundaries undefined
    PREFERENCES = "preferences"  # Style/convention choices


@dataclass
class PlanningQuestion:
    """A clarifying question asked during planning.

    Attributes:
        id: Unique identifier for the question
        question: The question text
        options: List of options (None for free text)
        default: Default answer if timeout or autonomous mode
        context: Explanation of why this question matters
        category: Question category for prioritization
    """

    id: str
    question: str
    options: list[str] | None
    default: str
    context: str
    category: QuestionCategory

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "question": self.question,
            "options": self.options,
            "default": self.default,
            "context": self.context,
            "category": self.category.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanningQuestion:
        """Create from dictionary."""
        category_str = data.get("category", "requirements")
        try:
            category = QuestionCategory(category_str)
        except ValueError:
            category = QuestionCategory.REQUIREMENTS

        return cls(
            id=data["id"],
            question=data["question"],
            options=data.get("options"),
            default=data.get("default", ""),
            context=data.get("context", ""),
            category=category,
        )


def extract_questions_from_response(response: str) -> list[PlanningQuestion]:
    """Extract planning questions from a Claude response.

    Looks for a ```questions...``` JSON block containing question objects.

    Args:
        response: Full Claude response text

    Returns:
        List of PlanningQuestion objects, empty if none found
    """
    # Find questions code blocks
    question_blocks = re.findall(r"```questions\s*(.*?)```", response, re.DOTALL)

    if not question_blocks:
        logger.debug("No questions block found in response")
        return []

    # Try each block
    for block in question_blocks:
        block = block.strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            logger.debug(f"Questions block failed to parse: {e}")
            continue

        # Should be a list of questions
        if not isinstance(data, list):
            logger.debug("Questions block is not a list")
            continue

        questions = []
        for i, q_data in enumerate(data):
            if not isinstance(q_data, dict):
                logger.debug(f"Question {i} is not an object")
                continue

            # Validate required fields
            if "id" not in q_data or "question" not in q_data:
                logger.debug(f"Question {i} missing required fields")
                continue

            try:
                question = PlanningQuestion.from_dict(q_data)
                questions.append(question)
            except (KeyError, TypeError) as e:
                logger.debug(f"Question {i} failed to parse: {e}")
                continue

        if questions:
            logger.debug(f"Extracted {len(questions)} questions from response")
            return questions

    return []


def ask_planning_questions(
    questions: list[PlanningQuestion],
    interaction: UserInteraction,
) -> dict[str, str]:
    """Ask planning questions using the interaction system.

    Args:
        questions: List of questions to ask
        interaction: UserInteraction instance for prompting

    Returns:
        Dictionary mapping question_id to answer string
    """
    from nelson.interaction import Question

    answers: dict[str, str] = {}

    for pq in questions:
        # Convert to interaction Question
        q = Question(
            id=pq.id,
            question=pq.question,
            options=pq.options,
            default=pq.default,
            context=pq.context,
        )

        answer = interaction.ask_question(q)
        answers[pq.id] = answer.response

    return answers


def format_answers_for_prompt(
    questions: list[PlanningQuestion],
    answers: dict[str, str],
) -> str:
    """Format questions and answers for inclusion in Claude prompt.

    Args:
        questions: Original questions asked
        answers: Dictionary mapping question_id to answer

    Returns:
        Formatted string suitable for prompt continuation
    """
    if not questions:
        return ""

    lines = ["", "## User Clarifications", ""]

    for q in questions:
        answer = answers.get(q.id, q.default)
        lines.append(f"**Q:** {q.question}")
        lines.append(f"**A:** {answer}")
        lines.append("")

    return "\n".join(lines)


def log_planning_questions(
    questions: list[PlanningQuestion],
    answers: dict[str, str],
    decisions_file: Path,
) -> None:
    """Log planning questions and answers to decisions file.

    Args:
        questions: Questions that were asked
        answers: User's answers (or defaults)
        decisions_file: Path to decisions.md file
    """
    if not questions:
        return

    timestamp = datetime.now().isoformat()

    lines = [
        "",
        "## Planning Clarifications",
        "",
        f"*Timestamp: {timestamp}*",
        "",
        "| Question | Answer | Default Used |",
        "|----------|--------|--------------|",
    ]

    for q in questions:
        answer = answers.get(q.id, q.default)
        used_default = "Yes" if answer == q.default else "No"
        # Escape pipe characters in question/answer for markdown table
        safe_question = q.question.replace("|", "\\|")
        safe_answer = answer.replace("|", "\\|")
        lines.append(f"| {safe_question} | {safe_answer} | {used_default} |")

    lines.append("")

    # Append to file
    with open(decisions_file, "a") as f:
        f.write("\n".join(lines))


# Pre-defined question templates for common scenarios
COMMON_QUESTIONS = {
    "auth_method": PlanningQuestion(
        id="auth_method",
        question="What authentication method should be used?",
        options=["JWT tokens", "Session cookies", "OAuth 2.0", "API keys"],
        default="JWT tokens",
        context="This determines the security model and affects frontend/backend integration.",
        category=QuestionCategory.ARCHITECTURE,
    ),
    "testing_level": PlanningQuestion(
        id="testing_level",
        question="What level of test coverage is needed?",
        options=["Unit tests only", "Unit + integration", "Full coverage with E2E"],
        default="Unit + integration",
        context="More testing increases confidence but takes more time.",
        category=QuestionCategory.SCOPE,
    ),
    "error_handling": PlanningQuestion(
        id="error_handling",
        question="How should errors be handled?",
        options=[
            "Simple exceptions",
            "Custom error types",
            "Full error hierarchy with codes",
        ],
        default="Custom error types",
        context="Affects debugging experience and API error responses.",
        category=QuestionCategory.ARCHITECTURE,
    ),
    "styling_approach": PlanningQuestion(
        id="styling_approach",
        question="What styling approach should be used?",
        options=["CSS modules", "Tailwind CSS", "Styled components", "Vanilla CSS"],
        default="CSS modules",
        context="Affects bundle size, DX, and consistency with existing code.",
        category=QuestionCategory.PREFERENCES,
    ),
}
