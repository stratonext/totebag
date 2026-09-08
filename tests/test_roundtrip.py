"""One roundtrip: create → persist to disk → reload with a fresh Store → context includes it."""

from pathlib import Path

import pytest

from totebag.context import build_context
from totebag.models import LinkType, ProjectStatus, ToolKind
from totebag.store import DescriptionRequired, Store


def test_roundtrip(tmp_path: Path) -> None:
    root = f"file://{tmp_path}/totebag"

    # --- write everything through one Store ---
    s = Store(root)
    s.init_workspace()
    project = s.create_project("Payments", description="Billing service")
    pid = project.id
    assert pid.startswith("prj_")

    s.add_note(pid, "idempotency key required")
    s.add_link(pid, url="https://stripe.com", name="Stripe", type=LinkType.documentation)
    doc = s.add_doc(pid, title="Runbook", body="# On-call\nrestart the worker", description="3am guide")

    asset_src = tmp_path / "arch.txt"
    asset_src.write_text("topology v2")
    asset = s.add_asset(pid, str(asset_src), description="the diagram")

    s.get_project(pid)  # ensure still loadable
    updated = s.get_project(pid)
    updated.description = "Handles invoicing."
    updated.status = ProjectStatus.active
    s.save_project(updated)

    # --- reload from disk with a brand-new Store instance ---
    s2 = Store(root)
    p2 = s2.get_project(pid)
    assert p2.description == "Handles invoicing."
    assert p2.notes == ["idempotency key required"]
    assert p2.links[0].name == "Stripe" and p2.links[0].type is LinkType.documentation
    assert p2.assets[0].description == "the diagram"
    assert p2.assets[0].size == len("topology v2")

    docs = s2.list_docs(pid)
    assert len(docs) == 1
    assert docs[0].id == doc.id and docs[0].description == "3am guide"
    assert "restart the worker" in docs[0].body

    # asset bytes survive the roundtrip
    assert s2.read_asset_bytes(pid, asset.id) == b"topology v2"

    # --- context blob contains the knowledge ---
    blob = build_context(s2, p2)
    for expected in ["Handles invoicing.", "idempotency key required", "Stripe", "Runbook", "3am guide"]:
        assert expected in blob

    # --- listing + search ---
    assert [pr.id for pr in s2.list_projects()] == [pid]
    hits = s2.search("idempotency")
    assert any(kind == "note" for _, kind, _, _ in hits)


def test_tasks_and_tools(tmp_path: Path) -> None:
    root = f"file://{tmp_path}/totebag"
    s = Store(root)
    s.init_workspace()
    pid = s.create_project("Payments", description="Billing service").id

    # a tool the project needs, with restore instructions
    s.add_tool(pid, name="stripe-cli", description="calls the Stripe API", restore="brew install stripe")
    # a task with an attachment in its own folder
    task = s.add_task(pid, title="Wire webhooks", description="handle Stripe webhook retries")
    att_src = tmp_path / "payload.json"
    att_src.write_text('{"id": 1}')
    s.add_task_asset(pid, task.id, str(att_src), description="sample webhook payload")

    # reload from a fresh Store
    s2 = Store(root)
    p2 = s2.get_project(pid)
    assert p2.tools[0].name == "stripe-cli" and p2.tools[0].kind is ToolKind.tool
    assert p2.tools[0].restore == "brew install stripe"

    tasks = s2.list_tasks(pid)
    assert len(tasks) == 1 and tasks[0].title == "Wire webhooks"
    assert tasks[0].assets[0].description == "sample webhook payload"

    # removing a task drops it from the list
    s2.remove_task(pid, task.id)
    assert s2.list_tasks(pid) == []

    blob = build_context(s2, s2.get_project(pid))
    for expected in ["stripe-cli", "restore:"]:
        assert expected in blob


def test_workspaces_are_isolated(tmp_path: Path) -> None:
    """Projects live under the active workspace; a second workspace is independent."""
    root = f"file://{tmp_path}/totebag"
    s = Store(root)
    default_ws = s.init_workspace()  # mints an id-workspace and marks it the default
    assert default_ws.id.startswith("wsp_")
    default_pid = s.create_project("In default", description="the default project").id

    other = s.create_workspace("scratch", description="a scratch workspace")
    assert other.id.startswith("wsp_") and other.id != default_ws.id

    # a store scoped to the new workspace sees none of the default's projects
    s_other = Store(root, workspace=other.id)
    assert s_other.list_projects() == []
    other_pid = s_other.create_project("In scratch", description="the scratch project").id

    # the default (no override) resolves from config; each workspace keeps only its own project
    assert [p.id for p in Store(root).list_projects()] == [default_pid]
    assert [p.id for p in Store(root, workspace=other.id).list_projects()] == [other_pid]

    # progressive discovery at workspace level, scoped to the target workspace
    wv = s.summarize_workspace(default_ws.id, recursive=True)
    assert wv["id"] == default_ws.id
    assert [p["id"] for p in wv["projects"]] == [default_pid]
    assert wv["projects"][0]["description"] == "the default project"

    # workspace CRUD: both listed, rename sticks, default is switchable, delete removes one
    assert {w.id for w in s.list_workspaces()} == {default_ws.id, other.id}
    s.update_workspace(other.id, "renamed")
    assert s.get_workspace(other.id).name == "renamed"
    s.set_default_workspace(other.id)
    assert Store(root).info()["workspace"] == other.id
    s.delete_workspace(other.id)
    assert [w.id for w in s.list_workspaces()] == [default_ws.id]


def test_description_required(tmp_path: Path) -> None:
    """Everything the caller stores must carry a description, or it's rejected."""
    s = Store(f"file://{tmp_path}/totebag")
    s.init_workspace()

    with pytest.raises(DescriptionRequired):
        s.create_workspace("no-desc")
    with pytest.raises(DescriptionRequired):
        s.create_project("no-desc")

    pid = s.create_project("P", description="a project").id

    with pytest.raises(DescriptionRequired):
        s.add_doc(pid, title="x", body="y", description="")
    with pytest.raises(DescriptionRequired):
        s.add_task(pid, title="x", description="   ")
    with pytest.raises(DescriptionRequired):
        s.add_tool(pid, name="x", description="")

    src = tmp_path / "f.txt"
    src.write_text("data")
    with pytest.raises(DescriptionRequired):
        s.add_asset(pid, str(src), description=None)
