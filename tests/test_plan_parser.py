"""Tests for plan_parser module."""

from pathlib import Path

import pytest

from nelson.plan_parser import (
    PhaseTaskSummary,
    PlanParser,
    Task,
    TaskStatus,
    load_plan,
)


@pytest.fixture
def sample_plan_content() -> str:
    """Sample plan.md content for testing."""
    return """# Implementation Plan

## Phase 1: PLAN
- [x] Read and analyze requirements
- [x] Create detailed plan
- [ ] Review with stakeholders

## Phase 2: IMPLEMENT
- [x] Create project structure
- [x] Add core modules
- [ ] Implement feature A
- [ ] Implement feature B
- [~] Implement feature C (deferred)

## Phase 3: REVIEW
- [ ] Code review
- [ ] Security review

Some random text that should be ignored.

## Phase 4: TEST
- [x] Unit tests
- [ ] Integration tests

## Notes
This should be ignored since it's not a phase.
"""


@pytest.fixture
def sample_plan_file(tmp_path: Path, sample_plan_content: str) -> Path:
    """Create a sample plan.md file."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(sample_plan_content)
    return plan_file


@pytest.fixture
def empty_plan_file(tmp_path: Path) -> Path:
    """Create an empty plan.md file."""
    plan_file = tmp_path / "empty_plan.md"
    plan_file.write_text("# Empty Plan\n\nNo tasks here.\n")
    return plan_file


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum values."""
        assert TaskStatus.COMPLETE.value == "x"
        assert TaskStatus.INCOMPLETE.value == " "
        assert TaskStatus.SKIPPED.value == "~"


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self) -> None:
        """Test creating a Task."""
        task = Task(
            line_number=5,
            status=TaskStatus.COMPLETE,
            content="Implement feature",
            phase=2,
        )
        assert task.line_number == 5
        assert task.status == TaskStatus.COMPLETE
        assert task.content == "Implement feature"
        assert task.phase == 2

    def test_task_is_frozen(self) -> None:
        """Test that Task is immutable."""
        task = Task(
            line_number=1,
            status=TaskStatus.INCOMPLETE,
            content="Test",
            phase=1,
        )
        with pytest.raises(AttributeError):
            task.status = TaskStatus.COMPLETE  # type: ignore


class TestPhaseTaskSummary:
    """Tests for PhaseTaskSummary dataclass."""

    def test_phase_summary_creation(self) -> None:
        """Test creating a PhaseTaskSummary."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=5,
            complete_tasks=2,
            incomplete_tasks=2,
            skipped_tasks=1,
        )
        assert summary.phase == 2
        assert summary.phase_name == "IMPLEMENT"
        assert summary.total_tasks == 5
        assert summary.complete_tasks == 2
        assert summary.incomplete_tasks == 2
        assert summary.skipped_tasks == 1

    def test_is_complete_with_incomplete_tasks(self) -> None:
        """Test is_complete returns False when incomplete tasks exist."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=5,
            complete_tasks=2,
            incomplete_tasks=2,
            skipped_tasks=1,
        )
        assert not summary.is_complete

    def test_is_complete_with_all_tasks_done(self) -> None:
        """Test is_complete returns True when all tasks are complete or skipped."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=5,
            complete_tasks=4,
            incomplete_tasks=0,
            skipped_tasks=1,
        )
        assert summary.is_complete

    def test_completion_percentage(self) -> None:
        """Test completion_percentage calculation."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=5,
            complete_tasks=2,
            incomplete_tasks=2,
            skipped_tasks=1,
        )
        # 2 complete out of 4 non-skipped = 50%
        assert summary.completion_percentage == 50.0

    def test_completion_percentage_all_skipped(self) -> None:
        """Test completion_percentage when all tasks are skipped."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=3,
            complete_tasks=0,
            incomplete_tasks=0,
            skipped_tasks=3,
        )
        assert summary.completion_percentage == 100.0

    def test_completion_percentage_no_tasks(self) -> None:
        """Test completion_percentage when there are no tasks."""
        summary = PhaseTaskSummary(
            phase=2,
            phase_name="IMPLEMENT",
            total_tasks=0,
            complete_tasks=0,
            incomplete_tasks=0,
            skipped_tasks=0,
        )
        assert summary.completion_percentage == 100.0


class TestPlanParser:
    """Tests for PlanParser class."""

    def test_parser_initialization(self, sample_plan_file: Path) -> None:
        """Test initializing a PlanParser."""
        parser = PlanParser(sample_plan_file)
        assert parser.plan_file == sample_plan_file

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        """Test parsing a non-existent file raises error."""
        parser = PlanParser(tmp_path / "nonexistent.md")
        with pytest.raises(FileNotFoundError):
            parser.parse()

    def test_parse_extracts_all_tasks(self, sample_plan_file: Path) -> None:
        """Test parsing extracts all tasks from file."""
        parser = PlanParser(sample_plan_file)
        tasks = parser.parse()

        # Count expected tasks: Phase 1 (3) + Phase 2 (5) + Phase 3 (2) + Phase 4 (2) = 12
        assert len(tasks) == 12

    def test_parse_extracts_task_status(self, sample_plan_file: Path) -> None:
        """Test parsing correctly identifies task status."""
        parser = PlanParser(sample_plan_file)
        tasks = parser.parse()

        # Phase 1 tasks
        phase1_tasks = [t for t in tasks if t.phase == 1]
        assert len(phase1_tasks) == 3
        assert phase1_tasks[0].status == TaskStatus.COMPLETE
        assert phase1_tasks[1].status == TaskStatus.COMPLETE
        assert phase1_tasks[2].status == TaskStatus.INCOMPLETE

        # Phase 2 has a skipped task
        phase2_tasks = [t for t in tasks if t.phase == 2]
        skipped_task = [t for t in phase2_tasks if t.status == TaskStatus.SKIPPED]
        assert len(skipped_task) == 1
        assert "feature C" in skipped_task[0].content

    def test_parse_associates_tasks_with_phases(self, sample_plan_file: Path) -> None:
        """Test parsing correctly associates tasks with their phase."""
        parser = PlanParser(sample_plan_file)
        tasks = parser.parse()

        # Verify each task has correct phase
        phase1_tasks = [t for t in tasks if t.phase == 1]
        phase1_keywords = ["analyze", "plan", "stakeholder"]
        assert all(any(kw in t.content for kw in phase1_keywords) for t in phase1_tasks)

        phase2_tasks = [t for t in tasks if t.phase == 2]
        phase2_keywords = ["structure", "modules", "feature"]
        assert all(any(kw in t.content for kw in phase2_keywords) for t in phase2_tasks)

    def test_get_tasks_by_phase(self, sample_plan_file: Path) -> None:
        """Test getting tasks for a specific phase."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        phase2_tasks = parser.get_tasks_by_phase(2)
        assert len(phase2_tasks) == 5

        phase4_tasks = parser.get_tasks_by_phase(4)
        assert len(phase4_tasks) == 2

        # Non-existent phase
        phase99_tasks = parser.get_tasks_by_phase(99)
        assert len(phase99_tasks) == 0

    def test_get_phase_summary(self, sample_plan_file: Path) -> None:
        """Test getting summary for a phase."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        summary = parser.get_phase_summary(2)
        assert summary is not None
        assert summary.phase == 2
        assert summary.phase_name == "IMPLEMENT"
        assert summary.total_tasks == 5
        assert summary.complete_tasks == 2
        assert summary.incomplete_tasks == 2
        assert summary.skipped_tasks == 1

    def test_get_phase_summary_nonexistent_phase(self, sample_plan_file: Path) -> None:
        """Test getting summary for non-existent phase returns None."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        summary = parser.get_phase_summary(99)
        assert summary is None

    def test_get_all_phase_summaries(self, sample_plan_file: Path) -> None:
        """Test getting summaries for all phases."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        summaries = parser.get_all_phase_summaries()
        assert len(summaries) == 4  # Phases 1, 2, 3, 4

        # Verify phases are in order
        assert summaries[0].phase == 1
        assert summaries[1].phase == 2
        assert summaries[2].phase == 3
        assert summaries[3].phase == 4

    def test_has_unchecked_tasks_true(self, sample_plan_file: Path) -> None:
        """Test has_unchecked_tasks returns True when incomplete tasks exist."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        assert parser.has_unchecked_tasks(2)  # Phase 2 has incomplete tasks
        assert parser.has_unchecked_tasks(3)  # Phase 3 has incomplete tasks

    def test_has_unchecked_tasks_false(self, sample_plan_file: Path) -> None:
        """Test has_unchecked_tasks returns False when no incomplete tasks exist."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        # We need a phase with all tasks complete/skipped
        # Let's create a custom file for this test
        all_complete_plan = parser.plan_file.parent / "all_complete.md"
        all_complete_plan.write_text("""
## Phase 1: PLAN
- [x] Task 1
- [x] Task 2
- [~] Task 3 (skipped)
""")
        parser2 = PlanParser(all_complete_plan)
        parser2.parse()

        assert not parser2.has_unchecked_tasks(1)

    def test_get_first_unchecked_task(self, sample_plan_file: Path) -> None:
        """Test getting the first unchecked task in a phase."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        first_unchecked = parser.get_first_unchecked_task(2)
        assert first_unchecked is not None
        assert first_unchecked.status == TaskStatus.INCOMPLETE
        assert "feature A" in first_unchecked.content

    def test_get_first_unchecked_task_none(self, sample_plan_file: Path) -> None:
        """Test getting first unchecked task when all are complete returns None."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        # Create a phase with all tasks complete
        all_complete_plan = parser.plan_file.parent / "all_complete2.md"
        all_complete_plan.write_text("""
## Phase 5: COMMIT
- [x] Commit all changes
""")
        parser2 = PlanParser(all_complete_plan)
        parser2.parse()

        first_unchecked = parser2.get_first_unchecked_task(5)
        assert first_unchecked is None

    def test_count_tasks_completed_recently(self, sample_plan_file: Path) -> None:
        """Test counting recently completed tasks."""
        parser = PlanParser(sample_plan_file)
        parser.parse()

        # Last 5 tasks in the file:
        # Phase 2: [~] skipped
        # Phase 3: [ ] incomplete
        # Phase 3: [ ] incomplete
        # Phase 4: [x] complete
        # Phase 4: [ ] incomplete
        recent_count = parser.count_tasks_completed_recently(5)
        assert recent_count == 1  # Only the Phase 4 unit test task

    def test_count_tasks_completed_recently_no_tasks(self, empty_plan_file: Path) -> None:
        """Test counting recently completed tasks with no tasks."""
        parser = PlanParser(empty_plan_file)
        parser.parse()

        recent_count = parser.count_tasks_completed_recently(5)
        assert recent_count == 0

    def test_parse_empty_file(self, empty_plan_file: Path) -> None:
        """Test parsing an empty plan file."""
        parser = PlanParser(empty_plan_file)
        tasks = parser.parse()

        assert len(tasks) == 0
        assert parser.get_all_phase_summaries() == []

    def test_parse_preserves_line_numbers(self, sample_plan_file: Path) -> None:
        """Test that parsing preserves original line numbers."""
        parser = PlanParser(sample_plan_file)
        tasks = parser.parse()

        # Line numbers should be sequential within the file
        # Just verify they're all positive and reasonable
        assert all(t.line_number > 0 for t in tasks)
        assert all(t.line_number < 100 for t in tasks)  # Sample file is small


class TestLoadPlan:
    """Tests for load_plan helper function."""

    def test_load_plan(self, sample_plan_file: Path) -> None:
        """Test load_plan helper function."""
        parser = load_plan(sample_plan_file)

        assert isinstance(parser, PlanParser)
        assert parser.plan_file == sample_plan_file
        # Verify it was already parsed
        assert len(parser._tasks) > 0

    def test_load_plan_missing_file(self, tmp_path: Path) -> None:
        """Test load_plan with missing file raises error."""
        with pytest.raises(FileNotFoundError):
            load_plan(tmp_path / "missing.md")
