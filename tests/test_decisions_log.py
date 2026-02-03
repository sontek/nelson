"""Tests for decisions_log module."""

from pathlib import Path

from nelson.decisions_log import (
    DecisionsLog,
    append_decision,
    append_phase_transition,
    append_summary,
    extract_recent_work,
    get_checkpoint_summary,
    should_compact,
    write_progress_checkpoint,
)
from nelson.phases import Phase


class TestDecisionsLog:
    """Test DecisionsLog class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test DecisionsLog initialization."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)
        assert log.log_path == log_path

    def test_append_decision_creates_file(self, tmp_path: Path) -> None:
        """Test appending decision creates file if it doesn't exist."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Create config module",
            what_i_did="Created src/nelson/config.py with NelsonConfig class",
            why="Need configuration management",
            result="Successfully created config module",
        )

        assert log_path.exists()

    def test_append_decision_creates_parent_directory(self, tmp_path: Path) -> None:
        """Test appending decision creates parent directories."""
        log_path = tmp_path / "subdir" / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Create config module",
            what_i_did="Created src/nelson/config.py",
            why="Need config",
            result="Success",
        )

        assert log_path.parent.exists()
        assert log_path.exists()

    def test_append_decision_adds_header(self, tmp_path: Path) -> None:
        """Test first decision adds header to new file."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Create config module",
            what_i_did="Created config",
            why="Need config",
            result="Success",
        )

        content = log_path.read_text()
        assert content.startswith("# Nelson Decisions Log\n\n")

    def test_append_decision_formats_correctly(self, tmp_path: Path) -> None:
        """Test decision entry is formatted correctly."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=5,
            phase=2,
            phase_name="Implementation",
            task="Create config module",
            what_i_did="Created src/nelson/config.py with NelsonConfig class",
            why="Need configuration management",
            result="Successfully created config module",
        )

        content = log_path.read_text()
        assert "## [Iteration 5] Phase 2: Implementation" in content
        assert "**Task:** Create config module" in content
        assert "**What I Did:**" in content
        assert "**Why:** Need configuration management" in content
        assert "**Result:** Successfully created config module" in content
        assert "---" in content

    def test_append_decision_adds_bullet_points(self, tmp_path: Path) -> None:
        """Test what_i_did without bullets gets them added."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test task",
            what_i_did="First action\nSecond action\nThird action",
            why="Testing bullets",
            result="Success",
        )

        content = log_path.read_text()
        assert "- First action" in content
        assert "- Second action" in content
        assert "- Third action" in content

    def test_append_decision_preserves_existing_bullets(self, tmp_path: Path) -> None:
        """Test what_i_did with bullets preserves them."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test task",
            what_i_did="- First action\n- Second action\n- Third action",
            why="Testing bullets",
            result="Success",
        )

        content = log_path.read_text()
        assert "- First action" in content
        assert "- Second action" in content
        assert "- Third action" in content

    def test_append_multiple_decisions(self, tmp_path: Path) -> None:
        """Test appending multiple decisions to same file."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=1,
            phase_name="Planning",
            task="Create plan",
            what_i_did="Created plan.md",
            why="Need plan",
            result="Success",
        )

        log.append_decision(
            iteration=2,
            phase=2,
            phase_name="Implementation",
            task="Create config",
            what_i_did="Created config.py",
            why="Need config",
            result="Success",
        )

        content = log_path.read_text()
        # Should only have one header
        assert content.count("# Nelson Decisions Log") == 1
        # Should have both iterations
        assert "## [Iteration 1] Phase 1: Planning" in content
        assert "## [Iteration 2] Phase 2: Implementation" in content

    def test_append_phase_transition(self, tmp_path: Path) -> None:
        """Test appending phase transition."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_phase_transition(iteration=5, from_phase=1, to_phase=2)

        content = log_path.read_text()
        assert "## Phase Transition (Iteration 5)" in content
        assert "**From**: Phase 1" in content
        assert "**To**: Phase 2" in content

    def test_append_summary(self, tmp_path: Path) -> None:
        """Test appending summary section."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        summary_text = "Phase 1 complete. Successfully analyzed nelson bash implementation."
        log.append_summary(summary_text)

        content = log_path.read_text()
        assert "## Summary" in content
        assert summary_text in content

    def test_mixed_entries(self, tmp_path: Path) -> None:
        """Test mixing decisions, transitions, and summaries."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=1,
            phase_name="Planning",
            task="Create plan",
            what_i_did="Created plan.md",
            why="Need plan",
            result="Success",
        )

        log.append_phase_transition(iteration=1, from_phase=1, to_phase=2)

        log.append_decision(
            iteration=2,
            phase=2,
            phase_name="Implementation",
            task="Create config",
            what_i_did="Created config.py",
            why="Need config",
            result="Success",
        )

        log.append_summary("All tasks complete")

        content = log_path.read_text()
        # Verify all entries are present
        assert "## [Iteration 1] Phase 1: Planning" in content
        assert "## Phase Transition (Iteration 1)" in content
        assert "## [Iteration 2] Phase 2: Implementation" in content
        assert "## Summary" in content


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_append_decision_convenience(self, tmp_path: Path) -> None:
        """Test append_decision convenience function."""
        log_path = tmp_path / "decisions.md"

        append_decision(
            log_path=log_path,
            iteration=3,
            phase=2,
            phase_name="Implementation",
            task="Test convenience function",
            what_i_did="Testing convenience function",
            why="To simplify API",
            result="Works correctly",
        )

        content = log_path.read_text()
        assert "## [Iteration 3] Phase 2: Implementation" in content
        assert "Test convenience function" in content

    def test_append_phase_transition_convenience(self, tmp_path: Path) -> None:
        """Test append_phase_transition convenience function."""
        log_path = tmp_path / "decisions.md"

        append_phase_transition(log_path=log_path, iteration=7, from_phase=3, to_phase=4)

        content = log_path.read_text()
        assert "## Phase Transition (Iteration 7)" in content
        assert "**From**: Phase 3" in content
        assert "**To**: Phase 4" in content

    def test_append_summary_convenience(self, tmp_path: Path) -> None:
        """Test append_summary convenience function."""
        log_path = tmp_path / "decisions.md"

        append_summary(log_path=log_path, summary="Testing summary function")

        content = log_path.read_text()
        assert "## Summary" in content
        assert "Testing summary function" in content


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_what_i_did(self, tmp_path: Path) -> None:
        """Test handling empty what_i_did."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test task",
            what_i_did="",
            why="Testing empty",
            result="Success",
        )

        content = log_path.read_text()
        assert "**What I Did:**" in content

    def test_multiline_why_and_result(self, tmp_path: Path) -> None:
        """Test multiline why and result fields."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        why = "This is a long explanation.\nIt spans multiple lines.\nTo provide context."
        result = "Successfully completed.\nAll tests pass.\nReady for next task."

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test task",
            what_i_did="Testing multiline",
            why=why,
            result=result,
        )

        content = log_path.read_text()
        assert why in content
        assert result in content

    def test_special_characters_in_content(self, tmp_path: Path) -> None:
        """Test handling special characters in content."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test with *markdown* and `code`",
            what_i_did="Added **bold** and _italic_ formatting",
            why="To test special chars: <>&\"'",
            result="Success with $variables and @mentions",
        )

        content = log_path.read_text()
        assert "*markdown*" in content
        assert "`code`" in content
        assert "**bold**" in content
        assert "_italic_" in content
        assert "$variables" in content
        assert "@mentions" in content

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Test handling unicode content."""
        log_path = tmp_path / "decisions.md"
        log = DecisionsLog(log_path)

        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Test unicode: 🚀 ✓ → ∞",
            what_i_did="Added emojis 🎉 and symbols",
            why="To support international users: 你好 мир",
            result="Success ✓",
        )

        content = log_path.read_text()
        assert "🚀" in content
        assert "✓" in content
        assert "→" in content
        assert "∞" in content
        assert "🎉" in content
        assert "你好" in content
        assert "мир" in content


class TestContextCompaction:
    """Test context compaction functions."""

    def test_should_compact_at_interval(self) -> None:
        """Test should_compact returns True at correct intervals."""
        # Default interval is 10
        assert not should_compact(0)
        assert not should_compact(5)
        assert not should_compact(9)
        assert should_compact(10)
        assert not should_compact(11)
        assert should_compact(20)
        assert should_compact(30)

    def test_should_compact_custom_interval(self) -> None:
        """Test should_compact with custom interval."""
        assert should_compact(5, compact_interval=5)
        assert not should_compact(3, compact_interval=5)
        assert should_compact(15, compact_interval=5)

    def test_write_progress_checkpoint(self, tmp_path: Path) -> None:
        """Test writing progress checkpoint."""
        log_path = tmp_path / "decisions.md"

        write_progress_checkpoint(
            log_path=log_path,
            original_task="Implement user authentication",
            current_phase=Phase.IMPLEMENT,
            cycle=1,
            iteration=10,
            tasks_completed=5,
            tasks_remaining=3,
            current_state="Working on login endpoint",
            approach="Implementing JWT-based authentication",
        )

        content = log_path.read_text()
        assert "PROGRESS CHECKPOINT (Iteration 10)" in content
        assert "Implement user authentication" in content
        assert "IMPLEMENT" in content
        assert "Cycle: 1" in content
        assert "5 done, 3 remaining" in content
        assert "JWT-based authentication" in content

    def test_write_progress_checkpoint_with_recent_work(self, tmp_path: Path) -> None:
        """Test checkpoint includes recent work items."""
        log_path = tmp_path / "decisions.md"

        write_progress_checkpoint(
            log_path=log_path,
            original_task="Build API",
            current_phase=Phase.IMPLEMENT,
            cycle=1,
            iteration=15,
            tasks_completed=3,
            tasks_remaining=2,
            current_state="In progress",
            approach="RESTful design",
            recent_work=["Created user model", "Added validation", "Wrote tests"],
        )

        content = log_path.read_text()
        assert "Recent Work:" in content
        assert "Created user model" in content
        assert "Added validation" in content
        assert "Wrote tests" in content

    def test_write_progress_checkpoint_with_blockers(self, tmp_path: Path) -> None:
        """Test checkpoint includes blockers."""
        log_path = tmp_path / "decisions.md"

        write_progress_checkpoint(
            log_path=log_path,
            original_task="Deploy service",
            current_phase=Phase.IMPLEMENT,
            cycle=1,
            iteration=20,
            tasks_completed=2,
            tasks_remaining=4,
            current_state="Blocked on infrastructure",
            approach="Docker-based deployment",
            blockers=["Waiting for AWS credentials", "Need VPN access"],
        )

        content = log_path.read_text()
        assert "Current Issues:" in content
        assert "Waiting for AWS credentials" in content
        assert "Need VPN access" in content

    def test_extract_recent_work(self, tmp_path: Path) -> None:
        """Test extracting recent work from decisions log."""
        log_path = tmp_path / "decisions.md"

        # Create a decisions log with work items
        log = DecisionsLog(log_path)
        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Create module",
            what_i_did="- Created config.py\n- Added validation\n- Wrote unit tests",
            why="Setup foundation",
            result="Success",
        )

        work_items = extract_recent_work(log_path)
        assert "Created config.py" in work_items
        assert "Added validation" in work_items
        assert "Wrote unit tests" in work_items

    def test_extract_recent_work_empty_file(self, tmp_path: Path) -> None:
        """Test extracting from empty or non-existent file."""
        log_path = tmp_path / "nonexistent.md"
        work_items = extract_recent_work(log_path)
        assert work_items == []

    def test_extract_recent_work_max_items(self, tmp_path: Path) -> None:
        """Test max_items limits returned work items."""
        log_path = tmp_path / "decisions.md"

        log = DecisionsLog(log_path)
        log.append_decision(
            iteration=1,
            phase=2,
            phase_name="Implementation",
            task="Many tasks",
            what_i_did="- Task 1\n- Task 2\n- Task 3\n- Task 4\n- Task 5\n- Task 6\n- Task 7",
            why="Testing",
            result="Done",
        )

        work_items = extract_recent_work(log_path, max_items=3)
        assert len(work_items) == 3
        # Should return most recent (last) items
        assert "Task 5" in work_items
        assert "Task 6" in work_items
        assert "Task 7" in work_items

    def test_get_checkpoint_summary(self, tmp_path: Path) -> None:
        """Test retrieving checkpoint summary."""
        log_path = tmp_path / "decisions.md"

        # Write a checkpoint
        write_progress_checkpoint(
            log_path=log_path,
            original_task="Test task",
            current_phase=Phase.IMPLEMENT,
            cycle=1,
            iteration=10,
            tasks_completed=5,
            tasks_remaining=3,
            current_state="Working",
            approach="Standard approach",
        )

        summary = get_checkpoint_summary(log_path)
        assert summary is not None
        assert "PROGRESS CHECKPOINT" in summary
        assert "Test task" in summary

    def test_get_checkpoint_summary_no_checkpoint(self, tmp_path: Path) -> None:
        """Test getting summary when no checkpoint exists."""
        log_path = tmp_path / "decisions.md"
        log_path.write_text("# Just a header\nSome content")

        summary = get_checkpoint_summary(log_path)
        assert summary is None

    def test_get_checkpoint_summary_nonexistent_file(self, tmp_path: Path) -> None:
        """Test getting summary from non-existent file."""
        log_path = tmp_path / "nonexistent.md"
        summary = get_checkpoint_summary(log_path)
        assert summary is None

    def test_multiple_checkpoints_returns_latest(self, tmp_path: Path) -> None:
        """Test that get_checkpoint_summary returns the latest checkpoint."""
        log_path = tmp_path / "decisions.md"

        # Write first checkpoint
        write_progress_checkpoint(
            log_path=log_path,
            original_task="First task",
            current_phase=Phase.PLAN,
            cycle=1,
            iteration=10,
            tasks_completed=2,
            tasks_remaining=5,
            current_state="Starting",
            approach="Initial approach",
        )

        # Write second checkpoint
        write_progress_checkpoint(
            log_path=log_path,
            original_task="First task",
            current_phase=Phase.IMPLEMENT,
            cycle=1,
            iteration=20,
            tasks_completed=5,
            tasks_remaining=2,
            current_state="Progressing",
            approach="Refined approach",
        )

        summary = get_checkpoint_summary(log_path)
        assert summary is not None
        assert "Iteration 20" in summary
        assert "IMPLEMENT" in summary
        assert "5 done, 2 remaining" in summary
