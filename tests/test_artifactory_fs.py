import asyncio

import pytest  # type: ignore

from arty_mc.core.artifactory_fs import ArtifactoryFS, FileEntry  # type: ignore


class FakeSession:
    def __init__(self):
        self.auth = ("u", "t")
        self._delete_fn = None

    def delete(self, url, timeout=30):
        if self._delete_fn:
            return self._delete_fn(url, timeout=timeout)
        resp = type("R", (), {"raise_for_status": lambda self: None})()
        return resp


class FakeAPI:
    def __init__(self):
        self._fake_session = FakeSession()
        self.session = type("S", (), {"session": self._fake_session})

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


def set_delete_fn(fs, fn):
    fs.api._fake_session._delete_fn = fn


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


def test_calculate_size_single_file(monkeypatch):
    fs = make_fs(monkeypatch)
    entry = type(
        "E", (), {"repo": "repo", "name": "firmware.iso", "is_dir": False, "size": 1048576}
    )
    assert fs.calculate_size(entry) == "(1.0 MB)"


def test_calculate_size_file_bytes(monkeypatch):
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "small.txt", "is_dir": False, "size": 512})
    assert fs.calculate_size(entry) == "(512 B)"


def test_calculate_size_file_no_size_returns_empty(monkeypatch):
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "file.txt", "is_dir": False, "size": None})
    assert fs.calculate_size(entry) == ""


def test_calculate_size_file_zero_size(monkeypatch):
    fs = make_fs(monkeypatch)
    entry = type("E", (), {"repo": "repo", "name": "empty.txt", "is_dir": False, "size": 0})
    assert fs.calculate_size(entry) == "(0 B)"


def test_calculate_size_directory_multiple_files(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.api.session.post = lambda url, data: {
        "results": [{"size": 1000}, {"size": 2000}, {"size": 3000}]
    }
    entry = type("E", (), {"repo": "repo", "name": "myfolder", "is_dir": True})
    result = fs.calculate_size(entry)
    assert "3 files" in result
    assert "KB" in result


def test_calculate_size_directory_single_file(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.api.session.post = lambda url, data: {"results": [{"size": 512}]}
    entry = type("E", (), {"repo": "repo", "name": "myfolder", "is_dir": True})
    result = fs.calculate_size(entry)
    assert "1 file" in result
    assert "files" not in result


def test_calculate_size_directory_empty(monkeypatch):
    fs = make_fs(monkeypatch)
    fs.api.session.post = lambda url, data: {"results": []}
    entry = type("E", (), {"repo": "repo", "name": "empty", "is_dir": True})
    result = fs.calculate_size(entry)
    assert "0 files" in result


def test_calculate_size_aql_uses_correct_endpoint(monkeypatch):
    fs = make_fs(monkeypatch)
    calls = []

    def fake_post(url, data):
        calls.append(url)
        return {"results": []}

    fs.api.session.post = fake_post
    entry = type("E", (), {"repo": "repo", "name": "folder", "is_dir": True})
    fs.calculate_size(entry)
    assert calls == ["/api/search/aql"]


def test_calculate_size_aql_fails_returns_empty(monkeypatch):
    fs = make_fs(monkeypatch)

    def fail(*a, **k):
        raise Exception("AQL error")

    fs.api.session.post = fail
    entry = type("E", (), {"repo": "repo", "name": "myfolder", "is_dir": True})
    assert fs.calculate_size(entry) == ""


def test_calculate_size_fmt_size_bytes(monkeypatch):
    fs = make_fs(monkeypatch)
    assert fs._fmt_size(0) == "0 B"
    assert fs._fmt_size(1023) == "1023 B"


def test_calculate_size_fmt_size_kb(monkeypatch):
    fs = make_fs(monkeypatch)
    assert fs._fmt_size(1024) == "1.0 KB"


def test_calculate_size_fmt_size_mb(monkeypatch):
    fs = make_fs(monkeypatch)
    assert fs._fmt_size(1024**2) == "1.0 MB"


def test_calculate_size_fmt_size_gb(monkeypatch):
    fs = make_fs(monkeypatch)
    assert fs._fmt_size(1024**3) == "1.0 GB"


def test_calculate_size_fmt_size_pb(monkeypatch):
    fs = make_fs(monkeypatch)
    assert "PB" in fs._fmt_size(2 * 1024**5)


def test_delete_item_issues_delete_request(monkeypatch):
    delete_calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, lambda url, timeout=30: (delete_calls.append(url), FakeResponse())[1])
    fs._delete_item("https://example.com/artifactory/repo/file.txt")
    assert len(delete_calls) == 1
    assert delete_calls[0] == "https://example.com/artifactory/repo/file.txt"


def test_delete_item_raises_on_failure(monkeypatch):
    def fake_delete(url, timeout=30):
        raise OSError("connection refused")

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, fake_delete)
    with pytest.raises(RuntimeError, match="Failed to delete"):
        fs._delete_item("https://example.com/artifactory/repo/file.txt")


def test_delete_item_progress_always_fires(monkeypatch):
    def fake_delete(url, timeout=30):
        raise OSError("timeout")

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, fake_delete)
    events = []
    with pytest.raises(RuntimeError):
        fs._delete_item(
            "https://example.com/repo/file.txt", progress_callback=lambda e, v: events.append(e)
        )
    assert "advance" in events


@pytest.mark.asyncio
async def test_delete_file(monkeypatch):
    delete_calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, lambda url, timeout=30: (delete_calls.append(url), FakeResponse())[1])
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

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, lambda url, timeout=30: (delete_calls.append(url), FakeResponse())[1])
    entry = type("E", (), {"repo": "repo", "name": "myfolder"})

    await fs.delete(entry)
    assert len(delete_calls) == 1


@pytest.mark.asyncio
async def test_delete_single_request(monkeypatch):
    delete_count = 0

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_delete(url, timeout=30):
        nonlocal delete_count
        delete_count += 1
        return FakeResponse()

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, fake_delete)
    entry = type("E", (), {"repo": "repo", "name": "anything"})

    await fs.delete(entry)
    assert delete_count == 1


@pytest.mark.asyncio
async def test_delete_cancel_before_start(monkeypatch):
    delete_calls = []

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, lambda url, timeout=30: delete_calls.append(url))
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    cancel_event = asyncio.Event()
    cancel_event.set()

    await fs.delete(entry, cancel_event=cancel_event)
    assert delete_calls == []


@pytest.mark.asyncio
async def test_delete_finish_fires_on_error(monkeypatch):
    def fake_delete(url, timeout=30):
        raise OSError("connection lost")

    fs = make_fs(monkeypatch)
    set_delete_fn(fs, fake_delete)
    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    with pytest.raises(RuntimeError):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_unexpected_exception_wrapped_as_runtime_error(monkeypatch):
    fs = make_fs(monkeypatch)

    async def fake_to_thread(fn, *args, **kwargs):
        raise ValueError("unexpected internal error")

    monkeypatch.setattr("asyncio.to_thread", fake_to_thread)

    entry = type("E", (), {"repo": "repo", "name": "file.txt"})
    events = []

    with pytest.raises(RuntimeError, match="Cannot reach Artifactory"):
        await fs.delete(entry, progress_callback=lambda e, v: events.append(e))

    assert "finish" in events
