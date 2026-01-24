"""Tests for goal-backward verification module."""

from pathlib import Path

from nelson.verification import (
    GoalVerification,
    VerificationCheck,
    VerificationLevel,
    check_exists,
    check_functional,
    check_substantive,
    check_wired,
    generate_verification_report,
    log_verification_results,
    run_verification,
)


class TestVerificationLevel:
    """Tests for VerificationLevel enum."""

    def test_level_values(self) -> None:
        """Test verification level enum values."""
        assert VerificationLevel.EXISTS.value == "exists"
        assert VerificationLevel.SUBSTANTIVE.value == "substantive"
        assert VerificationLevel.WIRED.value == "wired"
        assert VerificationLevel.FUNCTIONAL.value == "functional"

    def test_level_from_string(self) -> None:
        """Test creating level from string."""
        assert VerificationLevel("exists") == VerificationLevel.EXISTS
        assert VerificationLevel("functional") == VerificationLevel.FUNCTIONAL


class TestVerificationCheck:
    """Tests for VerificationCheck dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic VerificationCheck creation."""
        check = VerificationCheck(
            level=VerificationLevel.EXISTS,
            target="src/auth.ts",
            expected_result="File exists",
        )

        assert check.level == VerificationLevel.EXISTS
        assert check.target == "src/auth.ts"
        assert check.expected_result == "File exists"
        assert check.passed is None
        assert check.actual_result is None

    def test_full_creation(self) -> None:
        """Test VerificationCheck with all fields."""
        check = VerificationCheck(
            level=VerificationLevel.FUNCTIONAL,
            target="curl localhost:3000",
            expected_result="200 OK",
            check_command="curl localhost:3000",
            actual_result="200 OK",
            passed=True,
            details=["Response time: 50ms"],
        )

        assert check.passed is True
        assert check.check_command == "curl localhost:3000"
        assert len(check.details) == 1

    def test_to_dict(self) -> None:
        """Test VerificationCheck serialization."""
        check = VerificationCheck(
            level=VerificationLevel.SUBSTANTIVE,
            target="main.py",
            expected_result="No stubs",
            passed=True,
        )

        data = check.to_dict()

        assert data["level"] == "substantive"
        assert data["target"] == "main.py"
        assert data["passed"] is True

    def test_from_dict(self) -> None:
        """Test VerificationCheck deserialization."""
        data = {
            "level": "wired",
            "target": "app.py -> utils.py",
            "expected_result": "Import exists",
            "actual_result": "Found import",
            "passed": True,
            "details": ["import utils"],
        }

        check = VerificationCheck.from_dict(data)

        assert check.level == VerificationLevel.WIRED
        assert check.passed is True
        assert "import utils" in check.details


class TestGoalVerification:
    """Tests for GoalVerification dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic GoalVerification creation."""
        goal = GoalVerification(goal="User can log in")

        assert goal.goal == "User can log in"
        assert goal.truths == []
        assert goal.artifacts == []
        assert goal.wiring == []
        assert goal.checks == []

    def test_full_creation(self) -> None:
        """Test GoalVerification with all fields."""
        goal = GoalVerification(
            goal="User can log in",
            truths=["Login form accepts credentials", "Session is created"],
            artifacts=["src/Login.tsx", "src/api/auth.ts"],
            wiring=[("Login.tsx", "api/auth")],
        )

        assert len(goal.truths) == 2
        assert len(goal.artifacts) == 2
        assert len(goal.wiring) == 1

    def test_to_dict(self) -> None:
        """Test GoalVerification serialization."""
        goal = GoalVerification(
            goal="Test goal",
            artifacts=["file.py"],
            wiring=[("a.py", "b.py")],
        )

        data = goal.to_dict()

        assert data["goal"] == "Test goal"
        assert data["artifacts"] == ["file.py"]
        assert data["wiring"] == [["a.py", "b.py"]]

    def test_from_dict(self) -> None:
        """Test GoalVerification deserialization."""
        data = {
            "goal": "Feature works",
            "truths": ["Truth 1"],
            "artifacts": ["file.py"],
            "wiring": [["a.py", "b.py"]],
        }

        goal = GoalVerification.from_dict(data)

        assert goal.goal == "Feature works"
        assert goal.wiring == [("a.py", "b.py")]

    def test_passed_no_checks(self) -> None:
        """Test passed property with no checks."""
        goal = GoalVerification(goal="Test")
        assert goal.passed is True

    def test_passed_all_pass(self) -> None:
        """Test passed property when all checks pass."""
        goal = GoalVerification(
            goal="Test",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    passed=True,
                ),
            ],
        )
        assert goal.passed is True

    def test_passed_some_fail(self) -> None:
        """Test passed property when some checks fail."""
        goal = GoalVerification(
            goal="Test",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    passed=True,
                ),
                VerificationCheck(
                    level=VerificationLevel.SUBSTANTIVE,
                    target="file.py",
                    expected_result="No stubs",
                    passed=False,
                ),
            ],
        )
        assert goal.passed is False

    def test_critical_failures(self) -> None:
        """Test critical_failures property."""
        goal = GoalVerification(
            goal="Test",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    passed=False,  # Not critical
                ),
                VerificationCheck(
                    level=VerificationLevel.SUBSTANTIVE,
                    target="file.py",
                    expected_result="No stubs",
                    passed=False,  # Critical
                ),
                VerificationCheck(
                    level=VerificationLevel.WIRED,
                    target="a -> b",
                    expected_result="Connected",
                    passed=False,  # Critical
                ),
            ],
        )

        critical = goal.critical_failures
        assert len(critical) == 2
        critical_levels = (VerificationLevel.SUBSTANTIVE, VerificationLevel.WIRED)
        assert all(c.level in critical_levels for c in critical)


class TestCheckExists:
    """Tests for check_exists function."""

    def test_file_exists(self, tmp_path: Path) -> None:
        """Test EXISTS check on existing file."""
        test_file = tmp_path / "exists.py"
        test_file.write_text("print('hello')")

        check = check_exists("exists.py", tmp_path)

        assert check.passed is True
        assert check.level == VerificationLevel.EXISTS
        assert "Exists" in check.actual_result

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test EXISTS check on missing file."""
        check = check_exists("missing.py", tmp_path)

        assert check.passed is False
        assert "Not found" in check.actual_result

    def test_directory_exists(self, tmp_path: Path) -> None:
        """Test EXISTS check on directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        check = check_exists("subdir", tmp_path)

        assert check.passed is True


class TestCheckSubstantive:
    """Tests for check_substantive function."""

    def test_clean_file(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check on clean file."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("""
def calculate(x, y):
    return x + y

class Calculator:
    def add(self, a, b):
        return a + b
""")

        check = check_substantive("clean.py", tmp_path)

        assert check.passed is True
        assert check.level == VerificationLevel.SUBSTANTIVE

    def test_file_with_todo(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check finds TODO."""
        test_file = tmp_path / "todo.py"
        test_file.write_text("""
def calculate(x, y):
    # TODO: implement this
    return 0
""")

        check = check_substantive("todo.py", tmp_path)

        assert check.passed is False
        assert "TODO" in str(check.details)

    def test_file_with_not_implemented(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check finds NotImplementedError."""
        test_file = tmp_path / "stub.py"
        test_file.write_text("""
def calculate(x, y):
    raise NotImplementedError
""")

        check = check_substantive("stub.py", tmp_path)

        assert check.passed is False
        assert any("NotImplementedError" in d for d in check.details)

    def test_file_with_pass_only(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check finds empty pass statement."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("""
def calculate(x, y):
    pass
""")

        check = check_substantive("empty.py", tmp_path)

        assert check.passed is False

    def test_missing_file(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check on missing file."""
        check = check_substantive("missing.py", tmp_path)

        assert check.passed is False
        assert "not found" in check.actual_result.lower()

    def test_directory(self, tmp_path: Path) -> None:
        """Test SUBSTANTIVE check on directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        check = check_substantive("subdir", tmp_path)

        assert check.passed is True  # Directories pass


class TestCheckWired:
    """Tests for check_wired function."""

    def test_python_import(self, tmp_path: Path) -> None:
        """Test WIRED check finds Python import."""
        source = tmp_path / "main.py"
        source.write_text("""
from utils import helper
import utils

def main():
    helper()
""")

        check = check_wired("main.py", "utils.py", tmp_path)

        assert check.passed is True
        assert check.level == VerificationLevel.WIRED

    def test_js_import(self, tmp_path: Path) -> None:
        """Test WIRED check finds JavaScript import."""
        source = tmp_path / "app.js"
        source.write_text("""
import { helper } from './utils';
const data = require('./data');
""")

        check = check_wired("app.js", "utils.js", tmp_path)

        assert check.passed is True

    def test_no_import(self, tmp_path: Path) -> None:
        """Test WIRED check when no import exists."""
        source = tmp_path / "main.py"
        source.write_text("""
def main():
    print('hello')
""")

        check = check_wired("main.py", "utils.py", tmp_path)

        assert check.passed is False
        assert "No connection" in check.actual_result

    def test_source_missing(self, tmp_path: Path) -> None:
        """Test WIRED check when source file missing."""
        check = check_wired("missing.py", "utils.py", tmp_path)

        assert check.passed is False
        assert "not found" in check.actual_result.lower()


class TestCheckFunctional:
    """Tests for check_functional function."""

    def test_successful_command(self, tmp_path: Path) -> None:
        """Test FUNCTIONAL check with successful command."""
        check = check_functional(
            check_command="echo 'hello world'",
            expected_result="hello",
            cwd=tmp_path,
        )

        assert check.passed is True
        assert check.level == VerificationLevel.FUNCTIONAL

    def test_failed_command(self, tmp_path: Path) -> None:
        """Test FUNCTIONAL check with failing command."""
        check = check_functional(
            check_command="exit 1",
            expected_result="success",
            cwd=tmp_path,
        )

        # Exit code 1 but "success" not in output
        assert check.passed is False

    def test_expected_in_output(self, tmp_path: Path) -> None:
        """Test FUNCTIONAL check matches expected output."""
        check = check_functional(
            check_command="echo 'status: OK'",
            expected_result="OK",
            cwd=tmp_path,
        )

        assert check.passed is True

    def test_timeout(self, tmp_path: Path) -> None:
        """Test FUNCTIONAL check timeout handling."""
        check = check_functional(
            check_command="sleep 10",
            expected_result="done",
            timeout=1,
            cwd=tmp_path,
        )

        assert check.passed is False
        assert "Timeout" in check.actual_result


class TestRunVerification:
    """Tests for run_verification function."""

    def test_run_all_checks(self, tmp_path: Path) -> None:
        """Test running verification with all check types."""
        # Create test files
        source = tmp_path / "main.py"
        source.write_text("from utils import helper\n")

        utils = tmp_path / "utils.py"
        utils.write_text("def helper(): pass\n")

        goal = GoalVerification(
            goal="Feature works",
            artifacts=["main.py", "utils.py"],
            wiring=[("main.py", "utils.py")],
        )

        result = run_verification(goal, tmp_path)

        assert len(result.checks) > 0
        # Should have EXISTS, SUBSTANTIVE, and WIRED checks
        levels = {c.level for c in result.checks}
        assert VerificationLevel.EXISTS in levels
        assert VerificationLevel.SUBSTANTIVE in levels
        assert VerificationLevel.WIRED in levels

    def test_missing_artifact_skips_later(self, tmp_path: Path) -> None:
        """Test that missing artifacts don't get SUBSTANTIVE checks."""
        goal = GoalVerification(
            goal="Feature works",
            artifacts=["missing.py"],
        )

        result = run_verification(goal, tmp_path)

        # Should have EXISTS check that failed
        exists_checks = [c for c in result.checks if c.level == VerificationLevel.EXISTS]
        assert len(exists_checks) == 1
        assert exists_checks[0].passed is False

    def test_functional_checks(self, tmp_path: Path) -> None:
        """Test running functional checks."""
        goal = GoalVerification(
            goal="Echo works",
            functional_checks=[
                {"command": "echo test", "expected": "test"},
            ],
        )

        result = run_verification(goal, tmp_path)

        func_checks = [c for c in result.checks if c.level == VerificationLevel.FUNCTIONAL]
        assert len(func_checks) == 1
        assert func_checks[0].passed is True


class TestGenerateVerificationReport:
    """Tests for generate_verification_report function."""

    def test_empty_report(self) -> None:
        """Test report with no checks."""
        goal = GoalVerification(goal="Test goal")

        report = generate_verification_report(goal)

        assert "Test goal" in report
        assert "No verification checks" in report

    def test_passed_report(self) -> None:
        """Test report with all passing checks."""
        goal = GoalVerification(
            goal="Feature works",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    actual_result="Exists",
                    passed=True,
                ),
            ],
        )

        report = generate_verification_report(goal)

        assert "PASSED" in report
        assert "1/1" in report

    def test_failed_report(self) -> None:
        """Test report with failing checks."""
        goal = GoalVerification(
            goal="Feature works",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    actual_result="Not found",
                    passed=False,
                ),
                VerificationCheck(
                    level=VerificationLevel.SUBSTANTIVE,
                    target="other.py",
                    expected_result="No stubs",
                    actual_result="Found TODO",
                    passed=False,
                    details=["TODO comment"],
                ),
            ],
        )

        report = generate_verification_report(goal)

        assert "FAILED" in report
        assert "0/2" in report or "Critical" in report


class TestLogVerificationResults:
    """Tests for log_verification_results function."""

    def test_log_results(self, tmp_path: Path) -> None:
        """Test logging verification results."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Decisions\n")

        goal = GoalVerification(
            goal="Test feature",
            checks=[
                VerificationCheck(
                    level=VerificationLevel.EXISTS,
                    target="file.py",
                    expected_result="Exists",
                    passed=True,
                ),
            ],
        )

        log_verification_results(goal, decisions_file)

        content = decisions_file.read_text()
        assert "Goal Verification" in content
        assert "Test feature" in content
        assert "EXISTS" in content
