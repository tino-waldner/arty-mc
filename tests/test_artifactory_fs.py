import asyncio

import pytest  # type: ignore

from arty_mc.core.artifactory_fs import ArtifactoryFS, FileEntry  # type: ignore


class FakeAPI:
    def __init__(self):
        self.session = type("S", (), {"session": type("A", (), {"auth": ("u", "t")})})

    def list_folder(self, repo, path):
        return [
            {"name": "b.txt", "is_dir": False},
            {"name": "a", "is_dir": True},
        ]


def make_fs(monkeypatch):
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )
    config = {
        "default_repo": "repo",
        "server": "https://example.com",
    }
    return ArtifactoryFS(config)


def test_fileentry_getitem_and_get():
    entry = FileEntry("repo", "file.txt", False, size=100)
    assert entry["name"] == "file.txt"
    assert entry.get("size") == 100
    assert entry.get("nonexistent", "default") == "default"


def test_cd_and_up(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.cd("folder")
    assert fs.path_str == "folder"
    fs.cd("sub")
    assert fs.path_str == "folder/sub"
    fs.up()
    assert fs.path_str == "folder"


def test_up_at_root(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.up()
    assert fs.path_str == ""


def test_path_builder(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.cd("repo")
    assert fs.path("file.txt") == "repo/file.txt"


def test_list(monkeypatch):
    fs = make_fs(monkeypatch)
    items = fs.list()
    assert items[0].name == "a"
    assert items[0].is_dir is True


def test_delete_item_file(monkeypatch):
    class FakeItem:
        def __init__(self):
            self.deleted = False

        def is_file(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            self.deleted = True

    fs = make_fs(monkeypatch)
    item = FakeItem()
    fs._delete_item(item)
    assert item.deleted


def test_delete_item_exceptions(monkeypatch):
    class FakeItem:
        def is_file(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            raise OSError("fail")

        def rmdir(self):
            raise OSError("fail")

    fs = make_fs(monkeypatch)
    with pytest.raises(RuntimeError, match="Failed to delete"):
        fs._delete_item(FakeItem())


def test_delete_item_rmdir_exception(monkeypatch):
    class FakeDir:
        def is_file(self):
            return False

        def is_dir(self):
            return True

        def unlink(self):
            pass

        def rmdir(self):
            raise OSError("fail")

    fs = make_fs(monkeypatch)
    fs._delete_item(FakeDir())


@pytest.mark.asyncio
async def test_delete_async(monkeypatch):
    class FakeNode:
        def __init__(self, name, children=None):
            self.name = name
            self.children = children or []

        def is_file(self):
            return not self.children

        def is_dir(self):
            return bool(self.children)

        def iterdir(self):
            return self.children

        def unlink(self):
            pass

        def rmdir(self):
            pass

    root = FakeNode("root", [FakeNode("file.txt")])
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: root,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})
    events = []

    def progress(evt, val):
        events.append(evt)

    await fs.delete(entry, progress_callback=progress)
    assert "start" in events
    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_cancel(monkeypatch):
    class FakeNode:
        def is_file(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            pass

        def rmdir(self):
            pass

    root = FakeNode()
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: root,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})
    cancel_event = asyncio.Event()
    cancel_event.set()  # early cancel

    await fs.delete(entry, cancel_event=cancel_event)


@pytest.mark.asyncio
async def test_delete_nested_with_exceptions(monkeypatch):
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )

    class FakeNode:
        def __init__(self, name, children=None):
            self.name = name
            self.children = children or []

        def is_file(self):
            return not self.children

        def is_dir(self):
            return True

        def iterdir(self):
            return self.children

        def unlink(self):
            pass  # file deletes succeed

        def rmdir(self):
            raise OSError("fail")

    nested = FakeNode("root", children=[FakeNode("child1"), FakeNode("child2")])
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: nested,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})
    events = []

    def progress(evt, val):
        events.append(evt)

    await fs.delete(entry, progress_callback=progress)
    assert "start" in events
    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_multiple_files_concurrency(monkeypatch):
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )

    class FakeNode:
        def __init__(self, name, children=None):
            self.name = name
            self.children = children or []

        def is_file(self):
            return not self.children

        def is_dir(self):
            return bool(self.children)

        def iterdir(self):
            return self.children

        def unlink(self):
            pass

        def rmdir(self):
            pass

    files = [FakeNode(f"file{i}") for i in range(5)]
    root = FakeNode("root", children=files)
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: root,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})
    events = []

    def progress(evt, val):
        events.append(evt)

    await fs.delete(entry, progress_callback=progress)
    assert "start" in events
    assert "finish" in events
    assert any(e == "add_total" for e in events)
    assert any(e == "advance" for e in events)


@pytest.mark.asyncio
async def test_delete_cancel_midloop(monkeypatch):
    class Node:
        def __init__(self, name, children=None):
            self.name = name
            self.children = children or []

        def is_file(self):
            return not self.children

        def is_dir(self):
            return bool(self.children)

        def iterdir(self):
            return self.children

        def unlink(self):
            pass

        def rmdir(self):
            pass

    root = Node("root", children=[Node(f"file{i}") for i in range(3)])
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: root,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})
    cancel_event = asyncio.Event()

    async def trigger_cancel():
        await asyncio.sleep(0.01)
        cancel_event.set()

    await asyncio.gather(fs.delete(entry, cancel_event=cancel_event), trigger_cancel())


@pytest.mark.asyncio
async def test_delete_iterdir_exception(monkeypatch):
    class Node:
        def is_file(self):
            return False

        def is_dir(self):
            return True

        def iterdir(self):
            raise OSError("fail")

        def unlink(self):
            pass

        def rmdir(self):
            pass

    root = Node()
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: root,
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "root"})

    with pytest.raises(RuntimeError, match="Connection lost"):
        await fs.delete(entry)


@pytest.mark.asyncio
async def test_delete_connection_lost_on_is_file(monkeypatch):
    """If is_file() raises mid-walk, RuntimeError propagates and finish is still called."""
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )

    class FlakyNode:
        def is_file(self):
            raise ConnectionError("connection reset")

        def is_dir(self):
            return False

        def iterdir(self):
            return []

        def unlink(self):
            pass

        def rmdir(self):
            pass

    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: FlakyNode(),
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    with pytest.raises(RuntimeError, match="Connection lost"):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_connection_lost_on_iterdir(monkeypatch):
    """If iterdir() raises, RuntimeError propagates and finish is still called."""
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )

    class FlakyDir:
        def is_file(self):
            return False

        def is_dir(self):
            return True

        def iterdir(self):
            raise ConnectionError("connection reset")

        def unlink(self):
            pass

        def rmdir(self):
            pass

    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: FlakyDir(),
    )

    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "folder"})
    events = []

    with pytest.raises(RuntimeError, match="Connection lost"):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_item_raises_on_unlink_failure(monkeypatch):
    """_delete_item raises RuntimeError if unlink fails."""

    class FailNode:
        def is_file(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            raise OSError("permission denied")

        def __str__(self):
            return "fake/file.txt"

    fs = make_fs(monkeypatch)
    with pytest.raises(RuntimeError, match="Failed to delete"):
        fs._delete_item(FailNode())


@pytest.mark.asyncio
async def test_delete_item_progress_always_fires(monkeypatch):
    class FailNode:
        def is_file(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            raise OSError("disk error")

        def __str__(self):
            return "fake/file.txt"

    fs = make_fs(monkeypatch)
    events = []

    with pytest.raises(RuntimeError):
        fs._delete_item(FailNode(), progress_callback=lambda e, v: events.append(e))

    assert "advance" in events


@pytest.mark.asyncio
async def test_delete_artifactory_path_construction_fails(monkeypatch):
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryAPI",
        lambda config: FakeAPI(),
    )
    monkeypatch.setattr(
        "arty_mc.core.artifactory_fs.ArtifactoryPath",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("refused")),
    )
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})

    with pytest.raises(RuntimeError, match="Cannot reach Artifactory"):
        await fs.delete(entry)
