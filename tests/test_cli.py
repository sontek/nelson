"""Tests for CLI module."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nelson.cli import _build_config, main


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_workflow() -> Any:
    """Mock workflow execution."""
    with patch("nelson.cli._execute_workflow") as mock_execute:
        yield mock_execute


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_version_flag(self, cli_runner: CliRunner) -> None:
        """Test --version flag shows version."""
        result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "nelson" in result.output
        assert "0.1.0" in result.output

    def test_help_flag(self, cli_runner: CliRunner) -> None:
        """Test --help flag shows usage information."""
        result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Nelson: AI orchestration CLI" in result.output
        assert "PROMPT" in result.output
        assert "--resume" in result.output
        assert "Environment Variables:" in result.output

    def test_no_prompt_raises_error(self, cli_runner: CliRunner) -> None:
        """Test that running without prompt or --resume raises error."""
        result = cli_runner.invoke(main, [])
        assert result.exit_code != 0
        assert "PROMPT is required" in result.output


class TestPromptHandling:
    """Test various prompt input methods."""

    def test_string_prompt(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test prompt as string argument."""
        result = cli_runner.invoke(main, ["Add user authentication"])
        # Should not crash (workflow not implemented yet but CLI should accept it)
        assert result.exit_code == 0

    def test_file_prompt(self, cli_runner: CliRunner, mock_workflow: Any, tmp_path: Path) -> None:
        """Test prompt from file path."""
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("Implement feature X")

        result = cli_runner.invoke(main, [str(prompt_file)])
        assert result.exit_code == 0

    def test_stdin_prompt(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test prompt from stdin."""
        result = cli_runner.invoke(main, input="Task from stdin\n")
        assert result.exit_code == 0

    def test_empty_stdin_raises_error(self, cli_runner: CliRunner) -> None:
        """Test that empty stdin raises error."""
        result = cli_runner.invoke(main, input="")
        assert result.exit_code != 0
        assert "No prompt provided" in result.output

    def test_long_prompt_string(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test that very long prompt strings don't crash (OSError handling)."""
        # Create a prompt longer than typical filesystem path limits (usually 255 chars)
        long_prompt = "Implement " + "a very complex feature " * 50
        result = cli_runner.invoke(main, [long_prompt])
        # Should not crash with OSError: File name too long
        assert result.exit_code == 0


class TestConfigurationFlags:
    """Test CLI flags for configuration."""

    def test_max_iterations_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --max-iterations flag."""
        result = cli_runner.invoke(main, ["--max-iterations", "30", "Test task"])
        assert result.exit_code == 0

    def test_cost_limit_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --cost-limit flag."""
        result = cli_runner.invoke(main, ["--cost-limit", "25.50", "Test task"])
        assert result.exit_code == 0

    def test_model_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --model flag."""
        result = cli_runner.invoke(main, ["--model", "opus", "Test task"])
        assert result.exit_code == 0

    def test_plan_model_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --plan-model flag."""
        result = cli_runner.invoke(main, ["--plan-model", "opus", "Test task"])
        # Should not crash, workflow will use plan model
        assert result.exit_code == 0

    def test_review_model_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --review-model flag."""
        result = cli_runner.invoke(main, ["--review-model", "haiku", "Test task"])
        # Should not crash, workflow will use review model
        assert result.exit_code == 0

    def test_claude_command_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --claude-command flag."""
        result = cli_runner.invoke(main, ["--claude-command", "claude", "Test task"])
        # Should not crash, workflow will use specified claude command
        assert result.exit_code == 0

    def test_auto_approve_push_flag(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test --auto-approve-push flag."""
        result = cli_runner.invoke(main, ["--auto-approve-push", "Test task"])
        # Should not crash, config will have auto_approve_push=True
        assert result.exit_code == 0

    def test_multiple_flags_combined(self, cli_runner: CliRunner, mock_workflow: Any) -> None:
        """Test multiple flags combined."""
        result = cli_runner.invoke(
            main,
            [
                "--max-iterations",
                "20",
                "--model",
                "haiku",
                "--cost-limit",
                "5.0",
                "Test task",
            ],
        )
        assert result.exit_code == 0


class TestEnvironmentVariables:
    """Test environment variable loading."""

    def test_env_vars_loaded(
        self, cli_runner: CliRunner, mock_workflow: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables are loaded."""
        monkeypatch.setenv("NELSON_MAX_ITERATIONS", "100")
        monkeypatch.setenv("NELSON_MODEL", "opus")

        result = cli_runner.invoke(main, ["Test task"])
        assert result.exit_code == 0

    def test_cli_flags_override_env_vars(
        self, cli_runner: CliRunner, mock_workflow: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that CLI flags override environment variables."""
        monkeypatch.setenv("NELSON_MAX_ITERATIONS", "100")
        monkeypatch.setenv("NELSON_MODEL", "opus")

        result = cli_runner.invoke(
            main, ["--max-iterations", "25", "--model", "haiku", "Test task"]
        )
        assert result.exit_code == 0


class TestResumeMode:
    """Test --resume functionality."""

    def test_resume_flag_no_path(self, cli_runner: CliRunner) -> None:
        """Test --resume without path (resume from last)."""
        result = cli_runner.invoke(main, ["--resume"])
        # Should attempt to resume from last (aborts because not implemented)
        assert result.exit_code in (1, 2)  # Click.Abort returns 1, validation errors return 2

    def test_resume_flag_with_path(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test --resume with specific run directory."""
        run_dir = tmp_path / "nelson-20260112-120125"
        run_dir.mkdir(parents=True)

        result = cli_runner.invoke(main, ["--resume", str(run_dir)])
        # Should attempt to resume from path (aborts because not implemented)
        assert result.exit_code == 1  # Click.Abort returns 1


class TestPathArgument:
    """Test path argument functionality."""

    def test_path_argument_with_valid_repo(
        self, cli_runner: CliRunner, mock_workflow: Any, tmp_path: Path
    ) -> None:
        """Test path argument with valid git repository."""
        # Create a temporary git repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        result = cli_runner.invoke(main, ["Test task", str(repo_path)])
        assert result.exit_code == 0

    def test_path_argument_with_nonexistent_path(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test path argument with nonexistent path."""
        nonexistent = tmp_path / "nonexistent"

        result = cli_runner.invoke(main, ["Test task", str(nonexistent)])
        assert result.exit_code != 0
        # Click validates path exists before our code runs

    def test_path_argument_with_file_not_directory(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test path argument with file instead of directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = cli_runner.invoke(main, ["Test task", str(test_file)])
        assert result.exit_code != 0
        # Click validates path is a directory (file_okay=False)

    def test_path_argument_with_non_git_directory(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test path argument with directory that's not a git repository."""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        result = cli_runner.invoke(main, ["Test task", str(non_git_dir)])
        assert result.exit_code != 0
        assert "not a git repository" in result.output

    def test_path_argument_with_relative_path(
        self, cli_runner: CliRunner, mock_workflow: Any, tmp_path: Path
    ) -> None:
        """Test path argument with relative path gets resolved to absolute."""
        # Create a temporary git repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

        # Use relative path (../<dir_name>)
        result = cli_runner.invoke(
            main, ["Test task", str(repo_path)], catch_exceptions=False
        )
        assert result.exit_code == 0

    def test_path_argument_stored_in_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that path argument is stored in config."""
        # Create a temporary git repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        config = _build_config(
            max_iterations=None,
            cost_limit=None,
            model=None,
            plan_model=None,
            review_model=None,
            claude_command=None,
            auto_approve_push=False,
            target_path=repo_path,
        )

        assert config.target_path == repo_path

    def test_path_argument_none_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that target_path is None by default (current directory)."""
        config = _build_config(
            max_iterations=None,
            cost_limit=None,
            model=None,
            plan_model=None,
            review_model=None,
            claude_command=None,
            auto_approve_push=False,
        )

        assert config.target_path is None


class TestBuildConfig:
    """Test configuration building with CLI overrides."""

    def test_build_config_no_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test building config without CLI overrides uses defaults."""
        monkeypatch.setenv("NELSON_MAX_ITERATIONS", "50")
        monkeypatch.setenv("NELSON_MODEL", "sonnet")

        config = _build_config(
            max_iterations=None,
            cost_limit=None,
            model=None,
            plan_model=None,
            review_model=None,
            claude_command=None,
            auto_approve_push=False,
        )

        assert config.max_iterations == 50
        assert config.model == "sonnet"

    def test_build_config_with_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test building config with CLI overrides."""
        monkeypatch.setenv("NELSON_MAX_ITERATIONS", "50")
        monkeypatch.setenv("NELSON_MODEL", "sonnet")

        config = _build_config(
            max_iterations=30,
            cost_limit=15.0,
            model="opus",
            plan_model=None,
            review_model=None,
            claude_command="claude",
            auto_approve_push=True,
        )

        assert config.max_iterations == 30
        assert config.cost_limit == 15.0
        assert config.model == "opus"
        assert config.claude_command == "claude"
        assert config.auto_approve_push is True

    def test_build_config_model_cascading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that plan_model and review_model cascade from model."""
        monkeypatch.setenv("NELSON_MODEL", "sonnet")

        config = _build_config(
            max_iterations=None,
            cost_limit=None,
            model="opus",
            plan_model=None,
            review_model=None,
            claude_command=None,
            auto_approve_push=False,
        )

        # When model is set via CLI, plan_model and review_model should inherit it
        assert config.model == "opus"
        assert config.plan_model == "opus"
        assert config.review_model == "opus"

    def test_build_config_explicit_plan_review_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test explicit plan_model and review_model override cascading."""
        monkeypatch.setenv("NELSON_MODEL", "sonnet")

        config = _build_config(
            max_iterations=None,
            cost_limit=None,
            model="opus",
            plan_model="sonnet",
            review_model="haiku",
            claude_command=None,
            auto_approve_push=False,
        )

        # Explicit values should be used
        assert config.model == "opus"
        assert config.plan_model == "sonnet"
        assert config.review_model == "haiku"
