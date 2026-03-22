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


def test_delete_item_issues_delete_request(monkeypatch):
    delete_calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_delete(url, auth=None, timeout=30):
        delete_calls.append(url)
        return FakeResponse()

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    fs._delete_item("https://example.com/artifactory/repo/file.txt")
    assert len(delete_calls) == 1
    assert delete_calls[0] == "https://example.com/artifactory/repo/file.txt"


def test_delete_item_raises_on_failure(monkeypatch):
    import requests as req

    def fake_delete(url, auth=None, timeout=30):
        raise req.exceptions.RequestException("connection refused")

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    with pytest.raises(RuntimeError, match="Failed to delete"):
        fs._delete_item("https://example.com/artifactory/repo/file.txt")


def test_delete_item_progress_always_fires(monkeypatch):
    """progress advance fires even when DELETE request fails."""
    import requests as req

    def fake_delete(url, auth=None, timeout=30):
        raise req.exceptions.RequestException("timeout")

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    events = []
    with pytest.raises(RuntimeError):
        fs._delete_item(
            "https://example.com/repo/file.txt", progress_callback=lambda e, v: events.append(e)
        )
    assert "advance" in events


@pytest.mark.asyncio
async def test_delete_file(monkeypatch):
    """Deleting a file issues exactly one DELETE request."""
    delete_calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_delete(url, auth=None, timeout=30):
        delete_calls.append(url)
        return FakeResponse()

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert len(delete_calls) == 1
    assert "start" in events
    assert "add_total" in events
    assert "advance" in events
    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_directory(monkeypatch):
    delete_calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_delete(url, auth=None, timeout=30):
        delete_calls.append(url)
        return FakeResponse()

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "myfolder"})

    await fs.delete(entry)
    assert len(delete_calls) == 1


@pytest.mark.asyncio
async def test_delete_single_request(monkeypatch):
    delete_count = 0

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_delete(url, auth=None, timeout=30):
        nonlocal delete_count
        delete_count += 1
        return FakeResponse()

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "anything"})

    await fs.delete(entry)
    assert delete_count == 1


@pytest.mark.asyncio
async def test_delete_cancel_before_start(monkeypatch):
    """If cancel is set before delete runs, no DELETE request is issued."""
    delete_calls = []

    def fake_delete(url, auth=None, timeout=30):
        delete_calls.append(url)

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    cancel_event = asyncio.Event()
    cancel_event.set()

    await fs.delete(entry, cancel_event=cancel_event)
    assert delete_calls == []


@pytest.mark.asyncio
async def test_delete_finish_fires_on_error(monkeypatch):
    """finish callback fires even when DELETE request fails."""
    import requests as req

    def fake_delete(url, auth=None, timeout=30):
        raise req.exceptions.RequestException("connection lost")

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    with pytest.raises(RuntimeError):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_unexpected_exception_wrapped_as_runtime_error(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

    call_count = 0

    def fake_delete(url, auth=None, timeout=30):
        return FakeResponse()

    monkeypatch.setattr("arty_mc.core.artifactory_fs.requests.delete", fake_delete)
    fs = make_fs(monkeypatch)

    # Patch asyncio.to_thread to raise an unexpected non-RuntimeError
    async def fake_to_thread(fn, *args, **kwargs):
        raise ValueError("unexpected internal error")

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    with pytest.raises(RuntimeError, match="Cannot reach Artifactory"):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events
