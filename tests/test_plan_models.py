"""Tests for plan models and wave computation."""

import pytest

from nelson.plan_models import (
    Plan,
    Task,
    TaskStatus,
    WaveComputationError,
    compute_waves,
)
from nelson.verification import (
    GoalVerification,
    VerificationCheck,
    VerificationLevel,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.SKIPPED.value == "skipped"


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self) -> None:
        """Test basic task creation."""
        task = Task(
            id="01",
            name="Test task",
            wave=1,
            depends_on=[],
            files=["test.py"],
            action="Do something",
            verify="echo ok",
            done_when="It works",
        )

        assert task.id == "01"
        assert task.name == "Test task"
        assert task.wave == 1
        assert task.depends_on == []
        assert task.files == ["test.py"]
        assert task.action == "Do something"
        assert task.verify == "echo ok"
        assert task.done_when == "It works"
        assert task.status == TaskStatus.PENDING

    def test_task_with_dependencies(self) -> None:
        """Test task with dependencies."""
        task = Task(
            id="02",
            name="Second task",
            wave=2,
            depends_on=["01"],
            files=[],
            action="Do second",
            verify=None,
            done_when="Complete",
        )

        assert task.depends_on == ["01"]
        assert task.verify is None

    def test_task_to_dict(self) -> None:
        """Test task serialization."""
        task = Task(
            id="01",
            name="Test",
            wave=1,
            depends_on=["00"],
            files=["a.py"],
            action="Do it",
            verify="check",
            done_when="Done",
            status=TaskStatus.COMPLETED,
        )

        data = task.to_dict()

        assert data["id"] == "01"
        assert data["name"] == "Test"
        assert data["wave"] == 1
        assert data["depends_on"] == ["00"]
        assert data["files"] == ["a.py"]
        assert data["action"] == "Do it"
        assert data["verify"] == "check"
        assert data["done_when"] == "Done"
        assert data["status"] == "completed"

    def test_task_from_dict(self) -> None:
        """Test task deserialization."""
        data = {
            "id": "03",
            "name": "Third",
            "wave": 2,
            "depends_on": ["01", "02"],
            "files": ["x.py", "y.py"],
            "action": "Do third",
            "verify": "verify.sh",
            "done_when": "All done",
            "status": "in_progress",
        }

        task = Task.from_dict(data)

        assert task.id == "03"
        assert task.name == "Third"
        assert task.wave == 2
        assert task.depends_on == ["01", "02"]
        assert task.files == ["x.py", "y.py"]
        assert task.action == "Do third"
        assert task.verify == "verify.sh"
        assert task.done_when == "All done"
        assert task.status == TaskStatus.IN_PROGRESS

    def test_task_from_dict_defaults(self) -> None:
        """Test task deserialization with missing optional fields."""
        data = {
            "id": "01",
            "name": "Minimal",
            "action": "Do it",
            "done_when": "Done",
        }

        task = Task.from_dict(data)

        assert task.wave == 1  # Default
        assert task.depends_on == []  # Default
        assert task.files == []  # Default
        assert task.verify is None  # Default
        assert task.status == TaskStatus.PENDING  # Default

    def test_task_from_dict_invalid_status(self) -> None:
        """Test task deserialization with invalid status."""
        data = {
            "id": "01",
            "name": "Test",
            "action": "Do it",
            "done_when": "Done",
            "status": "invalid_status",
        }

        task = Task.from_dict(data)

        assert task.status == TaskStatus.PENDING  # Falls back to pending

    def test_task_is_ready_no_deps(self) -> None:
        """Test is_ready with no dependencies."""
        task = Task(
            id="01",
            name="Test",
            wave=1,
            depends_on=[],
            files=[],
            action="Do it",
            verify=None,
            done_when="Done",
        )

        assert task.is_ready(set()) is True
        assert task.is_ready({"other"}) is True

    def test_task_is_ready_with_deps(self) -> None:
        """Test is_ready with dependencies."""
        task = Task(
            id="02",
            name="Test",
            wave=2,
            depends_on=["01"],
            files=[],
            action="Do it",
            verify=None,
            done_when="Done",
        )

        assert task.is_ready(set()) is False
        assert task.is_ready({"other"}) is False
        assert task.is_ready({"01"}) is True
        assert task.is_ready({"01", "other"}) is True

    def test_task_is_ready_multiple_deps(self) -> None:
        """Test is_ready with multiple dependencies."""
        task = Task(
            id="03",
            name="Test",
            wave=3,
            depends_on=["01", "02"],
            files=[],
            action="Do it",
            verify=None,
            done_when="Done",
        )

        assert task.is_ready({"01"}) is False
        assert task.is_ready({"02"}) is False
        assert task.is_ready({"01", "02"}) is True


class TestPlan:
    """Tests for Plan dataclass."""

    def test_plan_creation(self) -> None:
        """Test basic plan creation."""
        plan = Plan(
            phase=1,
            name="Test Plan",
            goal="Test the plan",
        )

        assert plan.phase == 1
        assert plan.name == "Test Plan"
        assert plan.goal == "Test the plan"
        assert plan.tasks == []

    def test_plan_with_tasks(self) -> None:
        """Test plan with tasks."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=1,
                depends_on=[],
                files=[],
                action="Do first",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=2,
                depends_on=["01"],
                files=[],
                action="Do second",
                verify=None,
                done_when="Done",
            ),
        ]

        plan = Plan(phase=1, name="Test", goal="Test", tasks=tasks)

        assert len(plan.tasks) == 2

    def test_plan_to_dict(self) -> None:
        """Test plan serialization."""
        plan = Plan(
            phase=2,
            name="Test Plan",
            goal="Test serialization",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                )
            ],
        )

        data = plan.to_dict()

        assert data["phase"] == 2
        assert data["name"] == "Test Plan"
        assert data["goal"] == "Test serialization"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "01"

    def test_plan_from_dict(self) -> None:
        """Test plan deserialization."""
        data = {
            "phase": 3,
            "name": "Loaded Plan",
            "goal": "Test loading",
            "tasks": [
                {
                    "id": "01",
                    "name": "Task 1",
                    "action": "Do it",
                    "done_when": "Done",
                },
                {
                    "id": "02",
                    "name": "Task 2",
                    "depends_on": ["01"],
                    "action": "Do more",
                    "done_when": "Complete",
                },
            ],
        }

        plan = Plan.from_dict(data)

        assert plan.phase == 3
        assert plan.name == "Loaded Plan"
        assert plan.goal == "Test loading"
        assert len(plan.tasks) == 2
        assert plan.tasks[1].depends_on == ["01"]

    def test_plan_get_task(self) -> None:
        """Test getting task by ID."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                ),
            ],
        )

        task = plan.get_task("01")
        assert task is not None
        assert task.name == "First"

        task = plan.get_task("02")
        assert task is not None
        assert task.name == "Second"

        task = plan.get_task("99")
        assert task is None

    def test_plan_mark_completed(self) -> None:
        """Test marking task as completed."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                )
            ],
        )

        assert plan.tasks[0].status == TaskStatus.PENDING

        result = plan.mark_completed("01")
        assert result is True
        assert plan.tasks[0].status == TaskStatus.COMPLETED

        result = plan.mark_completed("99")
        assert result is False

    def test_plan_mark_skipped(self) -> None:
        """Test marking task as skipped."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                )
            ],
        )

        result = plan.mark_skipped("01")
        assert result is True
        assert plan.tasks[0].status == TaskStatus.SKIPPED

    def test_plan_mark_in_progress(self) -> None:
        """Test marking task as in progress."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                )
            ],
        )

        result = plan.mark_in_progress("01")
        assert result is True
        assert plan.tasks[0].status == TaskStatus.IN_PROGRESS

    def test_plan_get_pending_tasks(self) -> None:
        """Test getting pending tasks."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="03",
                    name="Third",
                    wave=2,
                    depends_on=[],
                    files=[],
                    action="Do even more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        pending = plan.get_pending_tasks()

        assert len(pending) == 2
        assert pending[0].id == "02"
        assert pending[1].id == "03"

    def test_plan_get_completed_ids(self) -> None:
        """Test getting completed task IDs."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        completed = plan.get_completed_ids()

        assert completed == {"01"}

    def test_plan_get_next_wave(self) -> None:
        """Test getting next executable wave."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="03",
                    name="Third",
                    wave=2,
                    depends_on=["01"],
                    files=[],
                    action="Do third",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        # First wave should have tasks 01 and 02
        next_wave = plan.get_next_wave()
        assert next_wave is not None
        assert len(next_wave) == 2
        assert {t.id for t in next_wave} == {"01", "02"}

        # Complete task 01
        plan.mark_completed("01")
        next_wave = plan.get_next_wave()
        assert next_wave is not None
        # Task 02 still pending in wave 1, task 03 now ready in wave 2
        # Should return wave 1 first
        assert len(next_wave) == 1
        assert next_wave[0].id == "02"

        # Complete task 02
        plan.mark_completed("02")
        next_wave = plan.get_next_wave()
        assert next_wave is not None
        assert len(next_wave) == 1
        assert next_wave[0].id == "03"

    def test_plan_get_next_wave_empty(self) -> None:
        """Test get_next_wave when all complete."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                )
            ],
        )

        next_wave = plan.get_next_wave()
        assert next_wave is None

    def test_plan_get_next_wave_blocked(self) -> None:
        """Test get_next_wave when tasks are blocked."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.IN_PROGRESS,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=2,
                    depends_on=["01"],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        # Task 01 is in progress, task 02 is blocked
        next_wave = plan.get_next_wave()
        assert next_wave is None

    def test_plan_is_complete(self) -> None:
        """Test is_complete check."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        assert plan.is_complete() is False

        plan.mark_completed("02")
        assert plan.is_complete() is True

    def test_plan_is_complete_with_skipped(self) -> None:
        """Test is_complete considers skipped tasks."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.COMPLETED,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.SKIPPED,
                ),
            ],
        )

        assert plan.is_complete() is True

    def test_plan_completion_percentage(self) -> None:
        """Test completion percentage calculation."""
        plan = Plan(
            phase=1,
            name="Test",
            goal="Test",
            tasks=[
                Task(
                    id="01",
                    name="First",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do it",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="02",
                    name="Second",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do more",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="03",
                    name="Third",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do third",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
                Task(
                    id="04",
                    name="Fourth",
                    wave=1,
                    depends_on=[],
                    files=[],
                    action="Do fourth",
                    verify=None,
                    done_when="Done",
                    status=TaskStatus.PENDING,
                ),
            ],
        )

        assert plan.completion_percentage() == 0.0

        plan.mark_completed("01")
        assert plan.completion_percentage() == 25.0

        plan.mark_completed("02")
        assert plan.completion_percentage() == 50.0

        plan.mark_skipped("03")  # Skipped also counts
        assert plan.completion_percentage() == 75.0

        plan.mark_completed("04")
        assert plan.completion_percentage() == 100.0

    def test_plan_completion_percentage_empty(self) -> None:
        """Test completion percentage with no tasks."""
        plan = Plan(phase=1, name="Empty", goal="Test")

        assert plan.completion_percentage() == 100.0

    def test_plan_verification_default(self) -> None:
        """Test plan has no verification by default."""
        plan = Plan(phase=1, name="Test", goal="Test")
        assert plan.verification is None

    def test_plan_with_verification(self) -> None:
        """Test plan with verification spec."""
        verification = GoalVerification(
            goal="User can log in",
            truths=["Login form exists", "Session is created"],
            artifacts=["src/login.py", "src/session.py"],
            wiring=[("login.py", "session.py")],
        )

        plan = Plan(
            phase=1,
            name="Auth Plan",
            goal="Implement login",
            verification=verification,
        )

        assert plan.verification is not None
        assert plan.verification.goal == "User can log in"
        assert len(plan.verification.truths) == 2
        assert len(plan.verification.artifacts) == 2
        assert len(plan.verification.wiring) == 1

    def test_plan_to_dict_with_verification(self) -> None:
        """Test plan serialization includes verification."""
        verification = GoalVerification(
            goal="Feature works",
            artifacts=["main.py"],
            wiring=[("main.py", "utils.py")],
        )

        plan = Plan(
            phase=1,
            name="Test Plan",
            goal="Test feature",
            verification=verification,
        )

        data = plan.to_dict()

        assert "verification" in data
        assert data["verification"]["goal"] == "Feature works"
        assert data["verification"]["artifacts"] == ["main.py"]
        assert data["verification"]["wiring"] == [["main.py", "utils.py"]]

    def test_plan_to_dict_without_verification(self) -> None:
        """Test plan serialization excludes verification when None."""
        plan = Plan(phase=1, name="Test", goal="Test")

        data = plan.to_dict()

        assert "verification" not in data

    def test_plan_from_dict_with_verification(self) -> None:
        """Test plan deserialization with verification."""
        data = {
            "phase": 1,
            "name": "Test Plan",
            "goal": "Test",
            "tasks": [],
            "verification": {
                "goal": "Feature complete",
                "truths": ["Truth 1", "Truth 2"],
                "artifacts": ["file.py"],
                "wiring": [["a.py", "b.py"]],
            },
        }

        plan = Plan.from_dict(data)

        assert plan.verification is not None
        assert plan.verification.goal == "Feature complete"
        assert plan.verification.truths == ["Truth 1", "Truth 2"]
        assert plan.verification.artifacts == ["file.py"]
        assert plan.verification.wiring == [("a.py", "b.py")]

    def test_plan_from_dict_without_verification(self) -> None:
        """Test plan deserialization without verification."""
        data = {
            "name": "Test",
            "goal": "Test goal",
        }

        plan = Plan.from_dict(data)

        assert plan.verification is None

    def test_plan_verification_with_checks(self) -> None:
        """Test plan with verification containing checks."""
        check = VerificationCheck(
            level=VerificationLevel.EXISTS,
            target="main.py",
            expected_result="File exists",
            passed=True,
        )

        verification = GoalVerification(
            goal="File created",
            artifacts=["main.py"],
            checks=[check],
        )

        plan = Plan(
            phase=1,
            name="Test",
            goal="Create file",
            verification=verification,
        )

        assert plan.verification.passed is True
        assert len(plan.verification.checks) == 1

    def test_plan_round_trip_with_verification(self) -> None:
        """Test plan serialization/deserialization round trip."""
        verification = GoalVerification(
            goal="Full feature",
            truths=["Works correctly"],
            artifacts=["src/main.py", "src/utils.py"],
            wiring=[("main.py", "utils.py")],
            functional_checks=[
                {"command": "echo test", "expected": "test"},
            ],
        )

        original = Plan(
            phase=2,
            name="Feature Plan",
            goal="Complete feature",
            tasks=[
                Task(
                    id="01",
                    name="First task",
                    wave=1,
                    depends_on=[],
                    files=["src/main.py"],
                    action="Create main",
                    verify=None,
                    done_when="Done",
                )
            ],
            verification=verification,
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = Plan.from_dict(data)

        # Verify all fields preserved
        assert restored.phase == original.phase
        assert restored.name == original.name
        assert restored.goal == original.goal
        assert len(restored.tasks) == len(original.tasks)
        assert restored.verification is not None
        assert restored.verification.goal == original.verification.goal
        assert restored.verification.truths == original.verification.truths
        assert restored.verification.artifacts == original.verification.artifacts
        assert restored.verification.wiring == original.verification.wiring


class TestComputeWaves:
    """Tests for wave computation."""

    def test_compute_waves_no_deps(self) -> None:
        """Test wave computation with no dependencies."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=0,
                depends_on=[],
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=0,
                depends_on=[],
                files=[],
                action="Do more",
                verify=None,
                done_when="Done",
            ),
        ]

        waves = compute_waves(tasks)

        assert len(waves) == 1
        assert 1 in waves
        assert len(waves[1]) == 2
        assert {t.id for t in waves[1]} == {"01", "02"}

    def test_compute_waves_linear(self) -> None:
        """Test wave computation with linear dependencies."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=0,
                depends_on=[],
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=0,
                depends_on=["01"],
                files=[],
                action="Do more",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="03",
                name="Third",
                wave=0,
                depends_on=["02"],
                files=[],
                action="Do third",
                verify=None,
                done_when="Done",
            ),
        ]

        waves = compute_waves(tasks)

        assert len(waves) == 3
        assert waves[1][0].id == "01"
        assert waves[2][0].id == "02"
        assert waves[3][0].id == "03"

    def test_compute_waves_diamond(self) -> None:
        """Test wave computation with diamond dependency pattern."""
        #    01
        #   /  \
        # 02    03
        #   \  /
        #    04
        tasks = [
            Task(
                id="01",
                name="First",
                wave=0,
                depends_on=[],
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=0,
                depends_on=["01"],
                files=[],
                action="Do more",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="03",
                name="Third",
                wave=0,
                depends_on=["01"],
                files=[],
                action="Do third",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="04",
                name="Fourth",
                wave=0,
                depends_on=["02", "03"],
                files=[],
                action="Do fourth",
                verify=None,
                done_when="Done",
            ),
        ]

        waves = compute_waves(tasks)

        assert len(waves) == 3
        assert waves[1][0].id == "01"
        assert {t.id for t in waves[2]} == {"02", "03"}
        assert waves[3][0].id == "04"

    def test_compute_waves_empty(self) -> None:
        """Test wave computation with empty task list."""
        waves = compute_waves([])
        assert waves == {}

    def test_compute_waves_circular_dependency(self) -> None:
        """Test wave computation detects circular dependencies."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=0,
                depends_on=["02"],
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=0,
                depends_on=["01"],
                files=[],
                action="Do more",
                verify=None,
                done_when="Done",
            ),
        ]

        with pytest.raises(WaveComputationError, match="Circular dependency"):
            compute_waves(tasks)

    def test_compute_waves_updates_task_wave(self) -> None:
        """Test that compute_waves updates the wave field on tasks."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=99,  # Will be overwritten
                depends_on=[],
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
            Task(
                id="02",
                name="Second",
                wave=99,  # Will be overwritten
                depends_on=["01"],
                files=[],
                action="Do more",
                verify=None,
                done_when="Done",
            ),
        ]

        compute_waves(tasks)

        assert tasks[0].wave == 1
        assert tasks[1].wave == 2

    def test_compute_waves_ignores_missing_deps(self) -> None:
        """Test that missing dependencies are ignored."""
        tasks = [
            Task(
                id="01",
                name="First",
                wave=0,
                depends_on=["missing"],  # Non-existent dependency
                files=[],
                action="Do it",
                verify=None,
                done_when="Done",
            ),
        ]

        waves = compute_waves(tasks)

        # Should treat as no dependencies
        assert len(waves) == 1
        assert waves[1][0].id == "01"
