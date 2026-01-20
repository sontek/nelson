"""Tests for decisions_log module."""

from pathlib import Path

from nelson.decisions_log import (
    DecisionsLog,
    append_decision,
    append_phase_transition,
    append_summary,
)


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
