"""Tests for planning questions module."""

from pathlib import Path

from nelson.interaction import InteractionConfig, InteractionMode, UserInteraction
from nelson.planning_questions import (
    COMMON_QUESTIONS,
    PlanningQuestion,
    QuestionCategory,
    ask_planning_questions,
    extract_questions_from_response,
    format_answers_for_prompt,
    log_planning_questions,
)


class TestQuestionCategory:
    """Tests for QuestionCategory enum."""

    def test_category_values(self) -> None:
        """Test category enum values."""
        assert QuestionCategory.REQUIREMENTS.value == "requirements"
        assert QuestionCategory.ARCHITECTURE.value == "architecture"
        assert QuestionCategory.SCOPE.value == "scope"
        assert QuestionCategory.PREFERENCES.value == "preferences"


class TestPlanningQuestion:
    """Tests for PlanningQuestion dataclass."""

    def test_question_creation(self) -> None:
        """Test basic question creation."""
        q = PlanningQuestion(
            id="q1",
            question="What framework?",
            options=["React", "Vue"],
            default="React",
            context="Framework choice matters",
            category=QuestionCategory.ARCHITECTURE,
        )

        assert q.id == "q1"
        assert q.question == "What framework?"
        assert q.options == ["React", "Vue"]
        assert q.default == "React"
        assert q.context == "Framework choice matters"
        assert q.category == QuestionCategory.ARCHITECTURE

    def test_question_no_options(self) -> None:
        """Test question without options (free text)."""
        q = PlanningQuestion(
            id="q2",
            question="What is the project name?",
            options=None,
            default="my-project",
            context="Need a name for the project",
            category=QuestionCategory.REQUIREMENTS,
        )

        assert q.options is None
        assert q.default == "my-project"

    def test_question_to_dict(self) -> None:
        """Test question serialization."""
        q = PlanningQuestion(
            id="q1",
            question="Test?",
            options=["A", "B"],
            default="A",
            context="Test context",
            category=QuestionCategory.SCOPE,
        )

        data = q.to_dict()

        assert data["id"] == "q1"
        assert data["question"] == "Test?"
        assert data["options"] == ["A", "B"]
        assert data["default"] == "A"
        assert data["context"] == "Test context"
        assert data["category"] == "scope"

    def test_question_from_dict(self) -> None:
        """Test question deserialization."""
        data = {
            "id": "q1",
            "question": "Test?",
            "options": ["X", "Y", "Z"],
            "default": "Y",
            "context": "Test",
            "category": "preferences",
        }

        q = PlanningQuestion.from_dict(data)

        assert q.id == "q1"
        assert q.question == "Test?"
        assert q.options == ["X", "Y", "Z"]
        assert q.default == "Y"
        assert q.context == "Test"
        assert q.category == QuestionCategory.PREFERENCES

    def test_question_from_dict_defaults(self) -> None:
        """Test question deserialization with missing optional fields."""
        data = {
            "id": "q1",
            "question": "Test?",
        }

        q = PlanningQuestion.from_dict(data)

        assert q.id == "q1"
        assert q.options is None
        assert q.default == ""
        assert q.context == ""
        assert q.category == QuestionCategory.REQUIREMENTS

    def test_question_from_dict_invalid_category(self) -> None:
        """Test question deserialization with invalid category."""
        data = {
            "id": "q1",
            "question": "Test?",
            "category": "invalid_category",
        }

        q = PlanningQuestion.from_dict(data)

        assert q.category == QuestionCategory.REQUIREMENTS  # Default


class TestExtractQuestionsFromResponse:
    """Tests for extract_questions_from_response function."""

    def test_extract_valid_questions(self) -> None:
        """Test extracting questions from valid response."""
        response = """
Here are my clarifying questions:

```questions
[
  {
    "id": "q1",
    "question": "Use TypeScript?",
    "options": ["Yes", "No"],
    "default": "Yes",
    "context": "Type safety",
    "category": "preferences"
  },
  {
    "id": "q2",
    "question": "Include tests?",
    "options": ["Yes", "No"],
    "default": "Yes",
    "context": "Code quality",
    "category": "scope"
  }
]
```

Let me know your preferences.
"""

        questions = extract_questions_from_response(response)

        assert len(questions) == 2
        assert questions[0].id == "q1"
        assert questions[0].question == "Use TypeScript?"
        assert questions[1].id == "q2"
        assert questions[1].category == QuestionCategory.SCOPE

    def test_extract_no_questions_block(self) -> None:
        """Test extraction with no questions block."""
        response = "Here is the plan without any questions."

        questions = extract_questions_from_response(response)

        assert questions == []

    def test_extract_empty_questions_list(self) -> None:
        """Test extraction with empty questions list."""
        response = """
No clarifications needed.

```questions
[]
```
"""

        questions = extract_questions_from_response(response)

        assert questions == []

    def test_extract_invalid_json(self) -> None:
        """Test extraction with invalid JSON."""
        response = """
```questions
{ invalid json }
```
"""

        questions = extract_questions_from_response(response)

        assert questions == []

    def test_extract_not_a_list(self) -> None:
        """Test extraction when JSON is not a list."""
        response = """
```questions
{"id": "q1", "question": "Test?"}
```
"""

        questions = extract_questions_from_response(response)

        assert questions == []

    def test_extract_missing_required_fields(self) -> None:
        """Test extraction skips questions with missing fields."""
        response = """
```questions
[
  {"id": "q1"},
  {"question": "Missing ID?"},
  {"id": "q3", "question": "Valid question"}
]
```
"""

        questions = extract_questions_from_response(response)

        # Only the valid question should be extracted
        assert len(questions) == 1
        assert questions[0].id == "q3"

    def test_extract_with_extra_whitespace(self) -> None:
        """Test extraction handles whitespace."""
        response = """
```questions

[
  {
    "id": "q1",
    "question": "Whitespace test?"
  }
]

```
"""

        questions = extract_questions_from_response(response)

        assert len(questions) == 1
        assert questions[0].question == "Whitespace test?"


class TestAskPlanningQuestions:
    """Tests for ask_planning_questions function."""

    def test_ask_questions_autonomous(self) -> None:
        """Test asking questions in autonomous mode returns defaults."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        questions = [
            PlanningQuestion(
                id="q1",
                question="Choose A or B?",
                options=["A", "B"],
                default="A",
                context="Test",
                category=QuestionCategory.REQUIREMENTS,
            ),
            PlanningQuestion(
                id="q2",
                question="Choose X or Y?",
                options=["X", "Y"],
                default="Y",
                context="Test",
                category=QuestionCategory.REQUIREMENTS,
            ),
        ]

        answers = ask_planning_questions(questions, interaction)

        assert answers["q1"] == "A"  # Default
        assert answers["q2"] == "Y"  # Default

    def test_ask_empty_questions(self) -> None:
        """Test asking empty questions list."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        answers = ask_planning_questions([], interaction)

        assert answers == {}


class TestFormatAnswersForPrompt:
    """Tests for format_answers_for_prompt function."""

    def test_format_answers(self) -> None:
        """Test formatting answers for prompt."""
        questions = [
            PlanningQuestion(
                id="q1",
                question="Framework?",
                options=["React", "Vue"],
                default="React",
                context="Test",
                category=QuestionCategory.ARCHITECTURE,
            ),
            PlanningQuestion(
                id="q2",
                question="Testing?",
                options=["Yes", "No"],
                default="Yes",
                context="Test",
                category=QuestionCategory.SCOPE,
            ),
        ]
        answers = {"q1": "Vue", "q2": "Yes"}

        formatted = format_answers_for_prompt(questions, answers)

        assert "## User Clarifications" in formatted
        assert "**Q:** Framework?" in formatted
        assert "**A:** Vue" in formatted
        assert "**Q:** Testing?" in formatted
        assert "**A:** Yes" in formatted

    def test_format_empty_questions(self) -> None:
        """Test formatting with no questions."""
        formatted = format_answers_for_prompt([], {})

        assert formatted == ""

    def test_format_uses_default_for_missing_answer(self) -> None:
        """Test that missing answers use default."""
        questions = [
            PlanningQuestion(
                id="q1",
                question="Test?",
                options=["A", "B"],
                default="B",
                context="Test",
                category=QuestionCategory.REQUIREMENTS,
            ),
        ]
        answers = {}  # No answer provided

        formatted = format_answers_for_prompt(questions, answers)

        assert "**A:** B" in formatted  # Default used


class TestLogPlanningQuestions:
    """Tests for log_planning_questions function."""

    def test_log_questions(self, tmp_path: Path) -> None:
        """Test logging questions to decisions file."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        questions = [
            PlanningQuestion(
                id="q1",
                question="Framework?",
                options=["React", "Vue"],
                default="React",
                context="Test",
                category=QuestionCategory.ARCHITECTURE,
            ),
        ]
        answers = {"q1": "Vue"}

        log_planning_questions(questions, answers, decisions_file)

        content = decisions_file.read_text()
        assert "## Planning Clarifications" in content
        assert "Framework?" in content
        assert "Vue" in content
        assert "No" in content  # Default not used

    def test_log_questions_default_used(self, tmp_path: Path) -> None:
        """Test logging when default was used."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        questions = [
            PlanningQuestion(
                id="q1",
                question="Test?",
                options=["A", "B"],
                default="A",
                context="Test",
                category=QuestionCategory.REQUIREMENTS,
            ),
        ]
        answers = {"q1": "A"}  # Same as default

        log_planning_questions(questions, answers, decisions_file)

        content = decisions_file.read_text()
        assert "Yes" in content  # Default was used

    def test_log_empty_questions(self, tmp_path: Path) -> None:
        """Test logging with no questions does nothing."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Existing Content\n")

        log_planning_questions([], {}, decisions_file)

        content = decisions_file.read_text()
        assert content == "# Existing Content\n"  # Unchanged

    def test_log_appends_to_existing(self, tmp_path: Path) -> None:
        """Test logging appends to existing content."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Previous Decisions\n\nSome content here.\n")

        questions = [
            PlanningQuestion(
                id="q1",
                question="New question?",
                options=["Yes", "No"],
                default="Yes",
                context="Test",
                category=QuestionCategory.SCOPE,
            ),
        ]
        answers = {"q1": "No"}

        log_planning_questions(questions, answers, decisions_file)

        content = decisions_file.read_text()
        assert "# Previous Decisions" in content
        assert "## Planning Clarifications" in content
        assert "New question?" in content

    def test_log_escapes_pipe_characters(self, tmp_path: Path) -> None:
        """Test that pipe characters are escaped in table."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        questions = [
            PlanningQuestion(
                id="q1",
                question="Use A | B?",
                options=["A", "B"],
                default="A",
                context="Test",
                category=QuestionCategory.REQUIREMENTS,
            ),
        ]
        answers = {"q1": "Option | with pipe"}

        log_planning_questions(questions, answers, decisions_file)

        content = decisions_file.read_text()
        assert "\\|" in content  # Pipes escaped


class TestCommonQuestions:
    """Tests for predefined common questions."""

    def test_common_questions_exist(self) -> None:
        """Test that common questions are defined."""
        assert "auth_method" in COMMON_QUESTIONS
        assert "testing_level" in COMMON_QUESTIONS
        assert "error_handling" in COMMON_QUESTIONS
        assert "styling_approach" in COMMON_QUESTIONS

    def test_common_questions_valid(self) -> None:
        """Test that common questions are valid."""
        for name, q in COMMON_QUESTIONS.items():
            assert isinstance(q, PlanningQuestion)
            assert q.id == name
            assert q.question
            assert q.options is not None
            assert q.default in q.options
            assert q.context
            assert isinstance(q.category, QuestionCategory)
