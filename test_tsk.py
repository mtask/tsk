"""
Tests for tsk.

Unit tests: pure functions, no CalDAV needed.
Integration tests: require TASK_CONFIG_PATH env var pointing at a real conf.yaml.
  They use (and clean up) a calendar named TEST on the configured server.

Run all:          pytest test_tsk.py
Unit tests only:  pytest test_tsk.py -m "not integration"
Integration only: pytest test_tsk.py -m integration
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

# ── Load tsk as a module (it has no .py extension) ───────────────────────────

_tsk_path = os.path.join(os.path.dirname(__file__), "tsk")
_loader = importlib.machinery.SourceFileLoader("tsk", _tsk_path)
_spec = importlib.util.spec_from_loader("tsk", _loader)
tsk = importlib.util.module_from_spec(_spec)
_loader.exec_module(tsk)

# ── Helpers ───────────────────────────────────────────────────────────────────

HAS_CONFIG = bool(os.environ.get("TASK_CONFIG_PATH"))
integration = pytest.mark.integration

TSK = [sys.executable, _tsk_path]


def run(*args, check=True):
    """Run tsk with TASK_CONFIG_PATH forwarded from the environment."""
    result = subprocess.run(
        TSK + list(args),
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"tsk {args} failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


# ── Unit: parse_due ───────────────────────────────────────────────────────────

class TestParseDue:
    def _approx(self, result, expected, seconds=5):
        diff = abs((result - expected).total_seconds())
        assert diff < seconds, f"{result} not within {seconds}s of {expected}"

    def test_minutes(self):
        now = datetime.now(timezone.utc)
        self._approx(tsk.parse_due("30m"), now + timedelta(minutes=30))

    def test_hours(self):
        now = datetime.now(timezone.utc)
        self._approx(tsk.parse_due("2h"), now + timedelta(hours=2))

    def test_days(self):
        now = datetime.now(timezone.utc)
        self._approx(tsk.parse_due("3d"), now + timedelta(days=3))

    def test_tomorrow(self):
        result = tsk.parse_due("tomorrow")
        expected_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        assert result.date() == expected_date
        assert result.hour == 9

    def test_tomorrow_with_hour(self):
        result = tsk.parse_due("tomorrow 14")
        assert result.hour == 14

    def test_absolute_date(self):
        result = tsk.parse_due("2026-06-01")
        assert result.date() == date(2026, 6, 1)

    def test_invalid(self):
        with pytest.raises(RuntimeError, match="Unsupported"):
            tsk.parse_due("next friday")


# ── Unit: format_due_display ──────────────────────────────────────────────────

class TestFormatDueDisplay:
    TODAY = date(2026, 3, 14)

    def test_none(self):
        assert tsk.format_due_display(None, self.TODAY) == ""

    def test_today(self):
        assert tsk.format_due_display(self.TODAY, self.TODAY) == "today"

    def test_tomorrow(self):
        assert tsk.format_due_display(date(2026, 3, 15), self.TODAY) == "tomorrow"

    def test_overdue_one(self):
        assert tsk.format_due_display(date(2026, 3, 13), self.TODAY) == "1d overdue"

    def test_overdue_many(self):
        assert tsk.format_due_display(date(2026, 3, 7), self.TODAY) == "7d overdue"

    def test_future(self):
        assert tsk.format_due_display(date(2026, 3, 19), self.TODAY) == "in 5d"


# ── Unit: sort_tasks ──────────────────────────────────────────────────────────

def _task(index, due_date=None, priority_raw="0"):
    return {
        "index": index,
        "due_date": due_date,
        "priority_raw": priority_raw,
        "summary": f"task {index}",
        "priority": tsk.PRIORITY_LABEL.get(priority_raw, ""),
        "due": None,
        "note": None,
        "status": "NEEDS-ACTION",
        "completed": False,
        "overdue": False,
        "due_today": False,
    }


class TestSortTasks:
    def test_sorts_by_due_ascending(self):
        tasks = [
            _task(1, date(2026, 4, 1)),
            _task(2, date(2026, 3, 20)),
            _task(3, date(2026, 3, 15)),
        ]
        result = tsk.sort_tasks(tasks)
        assert [t["index"] for t in result] == [3, 2, 1]

    def test_nulls_last(self):
        tasks = [
            _task(1, None),
            _task(2, date(2026, 3, 15)),
        ]
        result = tsk.sort_tasks(tasks)
        assert result[0]["index"] == 2
        assert result[1]["index"] == 1

    def test_same_due_sorted_by_priority(self):
        d = date(2026, 3, 20)
        tasks = [
            _task(1, d, "9"),   # low
            _task(2, d, "1"),   # high
            _task(3, d, "5"),   # medium
        ]
        result = tsk.sort_tasks(tasks)
        assert [t["index"] for t in result] == [2, 3, 1]

    def test_all_no_due_sorted_by_priority(self):
        tasks = [_task(1, None, "9"), _task(2, None, "1"), _task(3, None, "5")]
        result = tsk.sort_tasks(tasks)
        assert [t["index"] for t in result] == [2, 3, 1]


# ── Unit: resolve_project ─────────────────────────────────────────────────────

class TestResolveProject:
    CONFIG = {"projects": {"inbox": {}, "work": {}}}

    def test_from_words(self):
        project, words = tsk.resolve_project(["@work", "Fix bug"], {}, self.CONFIG)
        assert project == "work"
        assert words == ["Fix bug"]

    def test_from_state(self):
        project, words = tsk.resolve_project(["Buy milk"], {"project": "inbox"}, self.CONFIG)
        assert project == "inbox"
        assert words == ["Buy milk"]

    def test_word_overrides_state(self):
        project, _ = tsk.resolve_project(["@work", "task"], {"project": "inbox"}, self.CONFIG)
        assert project == "work"

    def test_no_project_exits(self):
        with pytest.raises(SystemExit):
            tsk.resolve_project(["task"], {}, self.CONFIG)

    def test_unknown_project_exits(self):
        with pytest.raises(SystemExit):
            tsk.resolve_project(["@unknown", "task"], {}, self.CONFIG)


# ── Unit: find_config ─────────────────────────────────────────────────────────

class TestFindConfig:
    def test_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tsk, "CONFIG_SEARCH_PATHS", [str(tmp_path / "missing.yaml")])
        assert tsk.find_config() is None

    def test_finds_existing(self, tmp_path, monkeypatch):
        cfg = tmp_path / "conf.yaml"
        cfg.write_text("projects: {}")
        monkeypatch.setattr(tsk, "CONFIG_SEARCH_PATHS", [str(cfg)])
        assert tsk.find_config() == str(cfg)


# ── Unit: arg parsing ─────────────────────────────────────────────────────────

class TestArgParsing:
    def _parse_add(self, *argv):
        """Simulate intermixed add parsing from main()."""
        _, p_add = tsk.build_parser()
        return p_add.parse_intermixed_args(list(argv))

    def test_add_text_after_flags(self):
        ns = self._parse_add("@koti", "-p", "high", "--due", "2026-03-31", "Pyydä vakuutustarjous if")
        assert ns.words == ["@koti", "Pyydä vakuutustarjous if"]
        assert ns.priority == "high"
        assert ns.due == "2026-03-31"

    def test_add_note(self):
        ns = self._parse_add("Buy milk", "--note", "2% fat")
        assert "Buy milk" in ns.words
        assert ns.note == "2% fat"

    def test_list_all_flag(self):
        parser, _ = tsk.build_parser()
        ns = parser.parse_args(["list", "--all"])
        assert ns.all is True

    def test_move_strips_at(self):
        parser, _ = tsk.build_parser()
        ns = parser.parse_args(["move", "3", "@work"])
        assert ns.target == "@work"   # stripping happens in cmd_move
        assert ns.index == 3


# ── Integration tests ─────────────────────────────────────────────────────────

@integration
class TestIntegration:
    """
    End-to-end tests against a real CalDAV server.
    Uses the TEST project (created if missing, cleaned up after each test).
    Requires TASK_CONFIG_PATH to point at a valid conf.yaml that already has
    at least one project configured, so credentials can be derived.
    """

    PROJECT = "TEST"

    @pytest.fixture(autouse=True)
    def setup_project(self):
        """Ensure TEST project exists; clean it before and after each test."""
        if not HAS_CONFIG:
            pytest.skip("TASK_CONFIG_PATH not set")
        # Create the project if it doesn't exist (idempotent: ignore error)
        r = run("project", "add", self.PROJECT, check=False)
        if r.returncode != 0 and "already exists" not in r.stdout:
            pytest.fail(f"Could not create TEST project: {r.stdout}{r.stderr}")

        run("use", self.PROJECT)
        self._cleanup()
        yield
        self._cleanup()

    def _cleanup(self):
        """Delete all tasks in the TEST project."""
        while True:
            r = run("list", self.PROJECT)
            # If there are tasks, delete index 1 repeatedly
            if "No tasks" in r.stdout or not r.stdout.strip():
                break
            result = run("del", "1", check=False)
            if result.returncode != 0:
                break

    # ── add / list ────────────────────────────────────────────────────────────

    def test_add_and_list(self):
        run("add", "Hello world")
        r = run("list", self.PROJECT)
        assert "Hello world" in r.stdout

    def test_add_with_priority_and_due(self):
        run("add", "-p", "high", "--due", "2026-12-31", "Priority task")
        r = run("list", self.PROJECT)
        assert "Priority task" in r.stdout
        assert "high" in r.stdout

    def test_add_with_note(self):
        run("add", "--note", "Remember the details", "Noted task")
        r = run("show", "1")
        assert "Remember the details" in r.stdout

    def test_add_at_project_override(self):
        run("add", f"@{self.PROJECT}", "Override task")
        r = run("list", self.PROJECT)
        assert "Override task" in r.stdout

    def test_add_flags_anywhere(self):
        """Flags may appear before or after the text."""
        run("add", f"@{self.PROJECT}", "-p", "high", "--due", "2026-12-31", "Mixed order task")
        r = run("list", self.PROJECT)
        assert "Mixed order task" in r.stdout

    # ── list filters ─────────────────────────────────────────────────────────

    def test_list_filter_priority(self):
        run("add", "-p", "high", "High task")
        run("add", "-p", "low", "Low task")
        r = run("list", "-p", "high")
        assert "High task" in r.stdout
        assert "Low task" not in r.stdout

    def test_list_filter_overdue(self):
        run("add", "--due", "2020-01-01", "Past task")
        run("add", "--due", "2099-01-01", "Future task")
        r = run("list", "--overdue")
        assert "Past task" in r.stdout
        assert "Future task" not in r.stdout

    def test_list_sorted_by_due(self):
        run("add", "--due", "2026-12-31", "Later task")
        run("add", "--due", "2026-04-01", "Earlier task")
        r = run("list", self.PROJECT)
        assert r.stdout.index("Earlier task") < r.stdout.index("Later task")

    # ── list --all ────────────────────────────────────────────────────────────

    def test_list_all_shows_completed(self):
        run("add", "Complete me")
        run("done", "1")
        r = run("list", "--all")
        assert "Complete me" in r.stdout
        assert "completed" in r.stdout.lower()

    def test_list_without_all_hides_completed(self):
        run("add", "Complete me")
        run("done", "1")
        r = run("list")
        assert "Complete me" not in r.stdout

    # ── show ──────────────────────────────────────────────────────────────────

    def test_show_displays_all_fields(self):
        run("add", "-p", "medium", "--due", "2026-06-01", "--note", "Test note", "Show task")
        r = run("show", "1")
        assert "Show task" in r.stdout
        assert "medium" in r.stdout
        assert "2026-06-01" in r.stdout
        assert "Test note" in r.stdout

    # ── edit ─────────────────────────────────────────────────────────────────

    def test_edit_summary(self):
        run("add", "Original title")
        run("edit", "1", "--summary", "Updated title")
        r = run("list")
        assert "Updated title" in r.stdout
        assert "Original title" not in r.stdout

    def test_edit_priority(self):
        run("add", "Task")
        run("edit", "1", "-p", "high")
        r = run("list")
        assert "high" in r.stdout

    def test_edit_priority_when_already_set(self):
        run("add", "-p", "low", "Task")
        run("edit", "1", "-p", "high")
        r = run("list")
        assert "high" in r.stdout

    def test_edit_due_clear(self):
        run("add", "--due", "2026-12-31", "Task with due")
        run("edit", "1", "--due", "none")
        r = run("show", "1")
        assert "2026-12-31" not in r.stdout

    def test_edit_note_and_clear(self):
        run("add", "--note", "initial note", "Task")
        run("edit", "1", "--note", "updated note")
        r = run("show", "1")
        assert "updated note" in r.stdout
        run("edit", "1", "--note", "none")
        r = run("show", "1")
        assert "updated note" not in r.stdout

    # ── done / del ───────────────────────────────────────────────────────────

    def test_done_removes_from_list(self):
        run("add", "Finish me")
        run("done", "1")
        r = run("list")
        assert "Finish me" not in r.stdout

    def test_del_removes_task(self):
        run("add", "Delete me")
        run("del", "1")
        r = run("list")
        assert "Delete me" not in r.stdout

    # ── move ─────────────────────────────────────────────────────────────────

    def test_move_to_other_project(self):
        # Use the first project in config as destination
        import yaml
        config_path = os.environ["TASK_CONFIG_PATH"]
        with open(config_path) as f:
            config = yaml.safe_load(f)
        projects = list(config["projects"].keys())
        other = next((p for p in projects if p != self.PROJECT), None)
        if other is None:
            pytest.skip("Need at least 2 projects to test move")

        run("add", "Move me")
        run("use", self.PROJECT)
        run("move", "1", other)

        # Should be gone from TEST
        r = run("list", self.PROJECT)
        assert "Move me" not in r.stdout

        # Should exist in other project — clean it up
        r2 = run("list", other)
        assert "Move me" in r2.stdout

        # Clean up the moved task
        other_list = run("list", other)
        lines = [l for l in other_list.stdout.splitlines() if "Move me" in l]
        if lines:
            # find index from the table
            run("use", other)
            idx = lines[0].strip().split()[0]
            run("del", idx, check=False)
            run("use", self.PROJECT)

    # ── next ─────────────────────────────────────────────────────────────────

    def test_next_shows_overdue(self):
        run("add", "--due", "2020-01-01", "Overdue task")
        run("add", "--due", "2099-01-01", "Far future task")
        r = run("next")
        assert "Overdue task" in r.stdout
        assert "Far future task" not in r.stdout

    def test_next_shows_high_priority(self):
        run("add", "-p", "high", "Urgent")
        run("add", "-p", "low", "Not urgent")
        r = run("next")
        assert "Urgent" in r.stdout
        assert "Not urgent" not in r.stdout
