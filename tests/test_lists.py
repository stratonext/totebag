"""Lists: create, batch-append schema-free entries, reload from disk, export to CSV."""

from pathlib import Path

import pytest

from totebag.store import DescriptionRequired, Store, entries_to_csv


def test_list_roundtrip_and_batches(tmp_path: Path) -> None:
    root = f"file://{tmp_path}/totebag"
    s = Store(root)
    s.init_workspace()
    pid = s.create_project("CRM", description="sales").id

    entry_list = s.create_list(pid, name="Prospects", description="Q3 target accounts")
    assert entry_list.id.startswith("lst_")

    # two batches with differing keys - no schema enforced, order preserved
    s.add_entries(pid, entry_list.id, [{"name": "Acme", "tier": "A"}, {"name": "Globex", "region": "EU"}])
    s.add_entries(pid, entry_list.id, [{"name": "Initech", "tags": ["x", "y"]}])

    # reload with a brand-new Store instance - entries survive the round-trip verbatim
    reloaded = Store(root).get_list(pid, entry_list.id)
    assert reloaded.name == "Prospects"
    assert reloaded.description == "Q3 target accounts"
    assert reloaded.entries == [
        {"name": "Acme", "tier": "A"},
        {"name": "Globex", "region": "EU"},
        {"name": "Initech", "tags": ["x", "y"]},
    ]


def test_remove_entry_by_index(tmp_path: Path) -> None:
    root = f"file://{tmp_path}/totebag"
    s = Store(root)
    s.init_workspace()
    pid = s.create_project("CRM", description="sales").id
    lst = s.create_list(pid, name="Prospects", description="targets")
    s.add_entries(pid, lst.id, [{"name": "Acme"}, {"name": "Globex"}, {"name": "Initech"}])

    removed = s.remove_entry(pid, lst.id, 1)  # 0-based: drops the middle entry
    assert removed == {"name": "Globex"}
    # persisted, and re-addable from what was returned
    assert [e["name"] for e in Store(root).get_list(pid, lst.id).entries] == ["Acme", "Initech"]
    s.add_entries(pid, lst.id, [removed])
    assert [e["name"] for e in s.get_list(pid, lst.id).entries] == ["Acme", "Initech", "Globex"]

    with pytest.raises(IndexError):
        s.remove_entry(pid, lst.id, 99)


def test_description_required(tmp_path: Path) -> None:
    s = Store(f"file://{tmp_path}/totebag")
    s.init_workspace()
    pid = s.create_project("CRM", description="sales").id
    with pytest.raises(DescriptionRequired):
        s.create_list(pid, name="Nameless", description="   ")


def test_list_lists_and_remove(tmp_path: Path) -> None:
    root = f"file://{tmp_path}/totebag"
    s = Store(root)
    s.init_workspace()
    pid = s.create_project("CRM", description="sales").id
    a = s.create_list(pid, name="A", description="first")
    b = s.create_list(pid, name="B", description="second")
    assert {lst.id for lst in s.list_lists(pid)} == {a.id, b.id}
    s.remove_list(pid, a.id)
    assert [lst.name for lst in s.list_lists(pid)] == ["B"]


def test_entries_to_csv_union_columns() -> None:
    # columns = union of keys ordered by first appearance; missing blank; nested -> JSON cell
    csv_text = entries_to_csv(
        [
            {"name": "Acme", "tier": "A"},
            {"name": "Globex", "region": "EU"},
            {"name": "Initech", "tags": ["x", "y"]},
        ]
    )
    assert csv_text == (
        "name,tier,region,tags\n"
        "Acme,A,,\n"
        "Globex,,EU,\n"
        'Initech,,,"[""x"", ""y""]"\n'
    )


def test_entries_to_csv_empty() -> None:
    assert entries_to_csv([]) == "\n"  # header row only, no columns


if __name__ == "__main__":  # runnable self-check on the CSV column logic
    assert entries_to_csv([{"a": 1}, {"b": 2}]) == "a,b\n1,\n,2\n"
    print("ok")
