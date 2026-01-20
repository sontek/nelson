#!/usr/bin/env python3
"""Diagnostic script to validate review phase scope hypothesis.

This script simulates what Phase 3 would see when reviewing "Phase 2 commits"
vs reviewing the actual PR diff.

Usage:
    cd /path/to/target/repo
    python /path/to/nelson/scripts/diagnose_review_scope.py
"""

import subprocess
import sys


def run_git(args: list[str]) -> str:
    """Run git command and return output."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main():
    print("=" * 60)
    print("REVIEW SCOPE DIAGNOSTIC")
    print("=" * 60)

    # Current branch
    branch = run_git(["branch", "--show-current"])
    print(f"\nCurrent branch: {branch}")

    # What Phase 3 sees: recent commits (Phase 2 commits)
    print("\n" + "-" * 60)
    print("WHAT PHASE 3 SEES (recent commits in this Nelson run):")
    print("-" * 60)

    # Get commits from last hour (typical Nelson run duration)
    recent_commits = run_git([
        "log", "--oneline", "--since=1 hour ago", "--no-merges"
    ])

    if recent_commits:
        print(f"Recent commits:\n{recent_commits}")
        # Get diff of those commits
        commit_count = len(recent_commits.split("\n"))
        diff_stat = run_git(["diff", "--stat", f"HEAD~{commit_count}", "HEAD"])
        print(f"\nFiles changed in recent commits:\n{diff_stat}")
    else:
        print("NO RECENT COMMITS - Phase 3 has nothing to review!")

    # What a PR review should see: diff against main/base branch
    print("\n" + "-" * 60)
    print("WHAT A PR REVIEW SHOULD SEE (diff against main):")
    print("-" * 60)

    # Try to find the base branch
    for base in ["main", "master", "origin/main", "origin/master"]:
        try:
            diff_stat = run_git(["diff", "--stat", f"{base}...HEAD"])
            if diff_stat:
                print(f"Diff against {base}:")
                print(diff_stat)

                # Count files
                file_count = len([l for l in diff_stat.split("\n") if "|" in l])
                print(f"\nTotal files changed vs {base}: {file_count}")
                break
        except Exception:
            continue
    else:
        print("Could not determine base branch diff")

    print("\n" + "=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    if not recent_commits:
        print("Phase 3 reviews 'Phase 2 commits' but there are NONE.")
        print("This confirms the hypothesis: review scope is too narrow.")
    else:
        print("Phase 3 has commits to review.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
