"""Tests for JSON plan parser and writer."""

from pathlib import Path

import pytest

from nelson.plan_models import Plan, Task, TaskStatus
from nelson.plan_parser_json import (
    PlanParseError,
    extract_plan_from_response,
    parse_json_plan,
    plan_to_markdown,
    write_json_plan,
)


class TestParseJsonPlan:
    """Tests for parse_json_plan function."""

    def test_parse_valid_plan(self, tmp_path: Path) -> None:
        """Test parsing a valid JSON plan."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(
            """{
            "phase": 1,
            "name": "Test Plan",
            "goal": "Test parsing",
            "tasks": [
                {
                    "id": "01",
                    "name": "First task",
                    "wave": 1,
                    "depends_on": [],
                    "files": ["test.py"],
                    "action": "Do something",
                    "verify": "echo ok",
                    "done_when": "It works"
                }
            ]
        }"""
        )

        plan = parse_json_plan(plan_file)

        assert plan.phase == 1
        assert plan.name == "Test Plan"
        assert plan.goal == "Test parsing"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].id == "01"
        assert plan.tasks[0].name == "First task"
        assert plan.tasks[0].files == ["test.py"]

    def test_parse_minimal_plan(self, tmp_path: Path) -> None:
        """Test parsing plan with minimal required fields."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(
            """{
            "name": "Minimal Plan",
            "tasks": [
                {
                    "id": "01",
                    "name": "Task",
                    "action": "Do it",
                    "done_when": "Done"
                }
            ]
        }"""
        )

        plan = parse_json_plan(plan_file)

        assert plan.name == "Minimal Plan"
        assert plan.phase == 1  # Default
        assert plan.goal == ""  # Default
        assert len(plan.tasks) == 1
        assert plan.tasks[0].wave == 1  # Default

    def test_parse_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing invalid JSON raises error."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text("{ invalid json }")

        with pytest.raises(PlanParseError, match="Invalid JSON"):
            parse_json_plan(plan_file)

    def test_parse_missing_name(self, tmp_path: Path) -> None:
        """Test parsing plan without name raises error."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text('{"tasks": []}')

        with pytest.raises(PlanParseError, match="missing required field: name"):
            parse_json_plan(plan_file)

    def test_parse_missing_tasks(self, tmp_path: Path) -> None:
        """Test parsing plan without tasks raises error."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text('{"name": "Test"}')

        with pytest.raises(PlanParseError, match="missing required field: tasks"):
            parse_json_plan(plan_file)

    def test_parse_tasks_not_list(self, tmp_path: Path) -> None:
        """Test parsing plan with non-list tasks raises error."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text('{"name": "Test", "tasks": "not a list"}')

        with pytest.raises(PlanParseError, match="tasks.*must be a list"):
            parse_json_plan(plan_file)

    def test_parse_task_missing_required_field(self, tmp_path: Path) -> None:
        """Test parsing task without required field raises error."""
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(
            """{
            "name": "Test",
            "tasks": [{"id": "01"}]
        }"""
        )

        with pytest.raises(PlanParseError, match="task 0 missing required field: name"):
            parse_json_plan(plan_file)

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """Test parsing nonexistent file raises error."""
        plan_file = tmp_path / "nonexistent.json"

        with pytest.raises(PlanParseError, match="Cannot read"):
            parse_json_plan(plan_file)


class TestWriteJsonPlan:
    """Tests for write_json_plan function."""

    def test_write_plan(self, tmp_path: Path) -> None:
        """Test writing a plan to JSON."""
        plan = Plan(
            phase=2,
            name="Written Plan",
            goal="Test writing",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=["a.py"],
                    action="Do it",
                    verify="check",
                    done_when="Done",
                )
            ],
        )
        plan_file = tmp_path / "output.json"

        write_json_plan(plan, plan_file)

        assert plan_file.exists()
        content = plan_file.read_text()
        assert '"name": "Written Plan"' in content
        assert '"phase": 2' in content
        assert '"id": "01"' in content

    def test_write_creates_directories(self, tmp_path: Path) -> None:
        """Test write creates parent directories."""
        plan = Plan(phase=1, name="Test", goal="Test", tasks=[])
        plan_file = tmp_path / "subdir" / "nested" / "plan.json"

        write_json_plan(plan, plan_file)

        assert plan_file.exists()

    def test_write_roundtrip(self, tmp_path: Path) -> None:
        """Test writing and reading produces same plan."""
        original = Plan(
            phase=3,
            name="Roundtrip Test",
            goal="Verify roundtrip",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=["a.py", "b.py"],
                    action="Do first",
                    verify="echo ok",
                    done_when="First done",
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=2,
                    depends_on=["01"],
                    files=[],
                    action="Do second",
                    verify=None,
                    done_when="Second done",
                    status=TaskStatus.COMPLETED,
                ),
            ],
        )
        plan_file = tmp_path / "roundtrip.json"

        write_json_plan(original, plan_file)
        loaded = parse_json_plan(plan_file)

        assert loaded.phase == original.phase
        assert loaded.name == original.name
        assert loaded.goal == original.goal
        assert len(loaded.tasks) == len(original.tasks)

        for i, task in enumerate(loaded.tasks):
            orig_task = original.tasks[i]
            assert task.id == orig_task.id
            assert task.name == orig_task.name
            assert task.wave == orig_task.wave
            assert task.depends_on == orig_task.depends_on
            assert task.files == orig_task.files
            assert task.action == orig_task.action
            assert task.verify == orig_task.verify
            assert task.done_when == orig_task.done_when
            assert task.status == orig_task.status


class TestExtractPlanFromResponse:
    """Tests for extract_plan_from_response function."""

    def test_extract_valid_plan(self) -> None:
        """Test extracting plan from response with valid JSON block."""
        response = """
Here is my plan:

```json
{
  "phase": 1,
  "name": "Feature Implementation",
  "goal": "Add new feature",
  "tasks": [
    {
      "id": "01",
      "name": "Create module",
      "wave": 1,
      "depends_on": [],
      "files": ["src/module.py"],
      "action": "Create the module",
      "verify": "python -c import",
      "done_when": "Module exists"
    }
  ]
}
```

I'll start implementing this now.
"""

        plan = extract_plan_from_response(response)

        assert plan is not None
        assert plan.name == "Feature Implementation"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].id == "01"

    def test_extract_no_json_block(self) -> None:
        """Test extraction returns None when no JSON block."""
        response = "Here is some text without any code blocks."

        plan = extract_plan_from_response(response)

        assert plan is None

    def test_extract_json_block_not_plan(self) -> None:
        """Test extraction returns None for non-plan JSON."""
        response = """
```json
{
  "config": "some_value",
  "other": 123
}
```
"""

        plan = extract_plan_from_response(response)

        assert plan is None

    def test_extract_invalid_json_block(self) -> None:
        """Test extraction handles invalid JSON gracefully."""
        response = """
```json
{ invalid json syntax }
```
"""

        plan = extract_plan_from_response(response)

        assert plan is None

    def test_extract_multiple_json_blocks(self) -> None:
        """Test extraction handles multiple JSON blocks."""
        response = """
Some config:
```json
{"not": "a plan"}
```

The actual plan:
```json
{
  "name": "Real Plan",
  "goal": "Do stuff",
  "tasks": [
    {
      "id": "01",
      "name": "Task",
      "action": "Do it",
      "done_when": "Done"
    }
  ]
}
```
"""

        plan = extract_plan_from_response(response)

        assert plan is not None
        assert plan.name == "Real Plan"

    def test_extract_with_extra_whitespace(self) -> None:
        """Test extraction handles various whitespace."""
        response = """
```json

{
  "name": "Whitespace Test",
  "goal": "Test whitespace handling",
  "tasks": [
    {
      "id": "01",
      "name": "Task",
      "action": "Do it",
      "done_when": "Done"
    }
  ]
}

```
"""

        plan = extract_plan_from_response(response)

        assert plan is not None
        assert plan.name == "Whitespace Test"


class TestPlanToMarkdown:
    """Tests for plan_to_markdown function."""

    def test_basic_conversion(self) -> None:
        """Test basic plan to markdown conversion."""
        plan = Plan(
            phase=1,
            name="Test Plan",
            goal="Test conversion",
            tasks=[
                Task(
                    id="01",
                    name="First task",
                    wave=1,
                    depends_on=[],
                    files=["test.py"],
                    action="Do something",
                    verify="echo ok",
                    done_when="It works",
                )
            ],
        )

        md = plan_to_markdown(plan)

        assert "# Test Plan" in md
        assert "**Phase:** 1" in md
        assert "**Goal:** Test conversion" in md
        assert "### Wave 1" in md
        assert "**01**: First task" in md
        assert "Action: Do something" in md
        assert "Done when: It works" in md
        assert "Files: test.py" in md
        assert "Verify: `echo ok`" in md

    def test_status_markers(self) -> None:
        """Test status markers in markdown."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="Pending",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="02",
                    name="In Progress",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.IN_PROGRESS,
                ),
                Task(
                    id="03",
                    name="Completed",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="04",
                    name="Skipped",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.SKIPPED,
                ),
            ],
        )

        md = plan_to_markdown(plan)

        assert "[ ] **01**" in md  # Pending
        assert "[~] **02**" in md  # In Progress
        assert "[x] **03**" in md  # Completed
        assert "[-] **04**" in md  # Skipped

    def test_multi_wave_plan(self) -> None:
        """Test multi-wave plan conversion."""
        plan = Plan(
            phase=1,
            name="Multi-Wave",
            goal="Test waves",
            tasks=[
                Task(
                    id="01",
                    name="Wave 1 Task",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do",
                    verify=None,
                    done_when="Done",
                ),
                Task(
                    id="02",
                    name="Wave 2 Task",
                    wave=2,
                    depends_on=["01"],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                ),
            ],
        )

        md = plan_to_markdown(plan)

        assert "### Wave 1" in md
        assert "### Wave 2" in md
        assert "Depends on: 01" in md

    def test_no_verify(self) -> None:
        """Test task without verify command."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="Task",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                )
            ],
        )

        md = plan_to_markdown(plan)

        assert "Verify:" not in md  # Should not include verify line
