"""CLI output-mode checks: terse by default, JSON under --json (incl. trailing, via main's hoist)."""

import json
import sys

from typer.testing import CliRunner

from totebag.cli import app, main

runner = CliRunner()


def _seed(root: str) -> str:
    runner.invoke(app, ["--root", root, "init"])
    r = runner.invoke(app, ["--root", root, "project", "create", "--name", "P", "--description", "d"])
    return r.output.strip()


def test_terse_vs_json_list(tmp_path):
    root = f"file://{tmp_path}/totebag"
    pid = _seed(root)

    terse = runner.invoke(app, ["--root", root, "project", "list"]).output
    assert pid in terse and "active" in terse

    data = json.loads(runner.invoke(app, ["--root", root, "--json", "project", "list"]).output)
    assert data[0]["id"] == pid


def test_json_hoisted_from_end(tmp_path, monkeypatch, capsys):
    root = f"file://{tmp_path}/totebag"
    _seed(root)
    # --json written after the subcommand still selects JSON (main hoists it to the front).
    monkeypatch.setattr(sys, "argv", ["totebag", "--root", root, "project", "list", "--json"])
    try:
        main()
    except SystemExit:
        pass
    json.loads(capsys.readouterr().out)  # parses → trailing --json produced JSON


def test_global_workspace_hoisted_from_end(tmp_path, monkeypatch, capsys):
    root = f"file://{tmp_path}/totebag"
    _seed(root)  # default workspace + project P
    other = runner.invoke(
        app, ["--root", root, "workspace", "create", "--name", "O", "--description", "d"]
    ).output.strip()
    # -w written AFTER the subcommand still targets `other` (main hoists it to the front).
    monkeypatch.setattr(
        sys, "argv", ["totebag", "--root", root, "--json", "workspace", "get", "--brief", "-w", other]
    )
    try:
        main()
    except SystemExit:
        pass
    assert json.loads(capsys.readouterr().out)["id"] == other


def test_doc_edit_updates_body_and_description(tmp_path):
    """A body edit succeeds on its own; --description refreshes it when the caller wants."""
    root = f"file://{tmp_path}/totebag"
    pid = _seed(root)
    did = runner.invoke(
        app, ["--root", root, "-p", pid, "doc", "add", "--title", "T", "--description", "orig", "--stdin"],
        input="v1",
    ).output.strip()

    # body-only edit → body changes, description untouched (no guard)
    assert runner.invoke(
        app, ["--root", root, "-p", pid, "doc", "edit", did, "--stdin"], input="v2"
    ).exit_code == 0
    doc = json.loads(runner.invoke(app, ["--root", root, "--json", "-p", pid, "doc", "get", did]).output)
    assert doc["body"] == "v2" and doc["description"] == "orig"

    # --description → refreshed
    assert runner.invoke(
        app, ["--root", root, "-p", pid, "doc", "edit", did, "--description", "new", "--stdin"], input="v3"
    ).exit_code == 0
    doc = json.loads(runner.invoke(app, ["--root", root, "--json", "-p", pid, "doc", "get", did]).output)
    assert doc["description"] == "new"


def test_doc_add_requires_description(tmp_path):
    root = f"file://{tmp_path}/totebag"
    pid = _seed(root)
    # missing --description → typer rejects (exit 2)
    assert runner.invoke(
        app, ["--root", root, "-p", pid, "doc", "add", "--title", "T", "--stdin"], input="v1"
    ).exit_code != 0


def test_workspace_resolves_to_active(tmp_path):
    """workspace get/update take no id when an active workspace is set (default or -w)."""
    root = f"file://{tmp_path}/totebag"
    _seed(root)
    active = json.loads(runner.invoke(app, ["--root", root, "--json", "config"]).output)["workspace"]

    # get with no id → the active workspace
    got = json.loads(runner.invoke(app, ["--root", root, "--json", "workspace", "get", "--brief"]).output)
    assert got["id"] == active

    # update with no id → the active workspace; -w targets another
    assert runner.invoke(app, ["--root", root, "workspace", "update", "--name", "Renamed"]).exit_code == 0
    other = runner.invoke(
        app, ["--root", root, "workspace", "create", "--name", "O", "--description", "d"]
    ).output.strip()
    got = json.loads(runner.invoke(app, ["--root", root, "--json", "-w", other, "workspace", "get", "--brief"]).output)
    assert got["id"] == other


def test_default_project_resolution(tmp_path):
    """`project use` sets a per-workspace default; commands resolve it, -p overrides, and a
    project outside the workspace is rejected."""
    root = f"file://{tmp_path}/totebag"
    pid = _seed(root)

    # no default and no -p → project-scoped command fails
    assert runner.invoke(app, ["--root", root, "note", "add", "x"]).exit_code != 0

    # set default, then commands work with no project given
    assert runner.invoke(app, ["--root", root, "project", "use", pid]).exit_code == 0
    assert runner.invoke(app, ["--root", root, "note", "add", "from default"]).exit_code == 0
    notes = json.loads(runner.invoke(app, ["--root", root, "--json", "note", "list"]).output)
    assert notes == ["from default"]

    # -p overrides; a bogus/out-of-workspace project id is rejected
    assert runner.invoke(app, ["--root", root, "-p", "prj_bogus", "note", "list"]).exit_code != 0
    # config reports the configured default
    cfg = json.loads(runner.invoke(app, ["--root", root, "--json", "config"]).output)
    assert cfg["default_project"] == pid and cfg["project"] == pid


def test_project_update_instructions_no_guard(tmp_path):
    root = f"file://{tmp_path}/totebag"
    pid = _seed(root)
    # editing instructions no longer forces a description decision
    assert runner.invoke(
        app, ["--root", root, "-p", pid, "project", "update", "--instructions", "do X"]
    ).exit_code == 0
    assert runner.invoke(
        app, ["--root", root, "-p", pid, "project", "update", "--name", "P2"]
    ).exit_code == 0
