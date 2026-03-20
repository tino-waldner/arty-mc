import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest  # type: ignore
from requests import Session as ReqSession  # type: ignore

from arty_mc.core import transfers  # type: ignore


def test_progress_file_reads(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("12345")
    events = []
    pf = transfers.ProgressFile(file_path, lambda ev, val: events.append((ev, val)))
    chunk = pf.read(2)
    assert chunk == b"12"
    assert pf.read_bytes == 2
    chunk2 = pf.read()
    assert chunk2 == b"345"
    assert pf.read_bytes == 5
    assert len(pf) == 5
    pf.close()


def test_progress_file_context_manager(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("abc")
    with transfers.ProgressFile(file_path) as pf:
        data = pf.read()
    assert data == b"abc"
    assert pf.file.closed


def test_progress_file_getattr(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("abc")
    pf = transfers.ProgressFile(file_path)
    assert hasattr(pf, "read")
    assert hasattr(pf, "close")
    assert pf.name == pf.file.name
    pf.close()


@pytest.mark.asyncio
async def test_progress_file_cancel(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("abc")
    cancel_event = asyncio.Event()
    cancel_event.set()
    pf = transfers.ProgressFile(file_path, cancel_event=cancel_event)
    with pytest.raises(asyncio.CancelledError):
        pf.read()


def test_create_session_retry():
    session = transfers.create_session()
    assert isinstance(session, ReqSession)
    assert "http://" in session.adapters
    assert "https://" in session.adapters


def test_upload_file_called(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(local=file_path, remote="remote/file.txt", is_dir=False)
    dummy_response = MagicMock()
    dummy_response.raise_for_status = MagicMock()
    dummy_session = MagicMock()
    dummy_session.put.return_value = dummy_response
    transfers.upload_file(entry, dummy_session)
    dummy_session.put.assert_called_once()
    dummy_response.raise_for_status.assert_called_once()


def test_upload_file_raises(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(local=file_path, remote="remote/file.txt", is_dir=False)
    dummy_response = MagicMock()
    dummy_response.raise_for_status.side_effect = Exception("fail")
    dummy_session = MagicMock()
    dummy_session.put.return_value = dummy_response
    with pytest.raises(Exception):
        transfers.upload_file(entry, dummy_session)


def test_upload_file_early_cancel_direct(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(local=file_path, remote="remote/file.txt", is_dir=False)
    cancel_event = asyncio.Event()
    cancel_event.set()
    dummy_session = MagicMock()
    transfers.upload_file(entry, dummy_session, cancel_event=cancel_event)
    dummy_session.put.assert_not_called()


@pytest.mark.asyncio
async def test_expand_upload_entries_with_file(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    entry = transfers.TransferEntry(local=file_path, remote="remote/file.txt", is_dir=False)
    expanded = await transfers.expand_upload_entries([entry])
    assert len(expanded) == 1
    assert expanded[0].local == file_path
    assert expanded[0].remote == "remote/file.txt"
    assert not expanded[0].is_dir


@pytest.mark.asyncio
async def test_expand_upload_entries_skips_dirs(tmp_path, monkeypatch):
    folder = tmp_path / "folder"
    folder.mkdir()
    subdir = folder / "subdir"
    subdir.mkdir()
    f1 = folder / "file.txt"
    f1.write_text("abc")

    class FakeArt:
        def __init__(self, path, auth=None):
            self.path = Path(path)

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return [f1, subdir]

        def relative_to(self, other):
            return Path(f1.name)

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)
    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)
    expanded = await transfers.expand_upload_entries([entry])
    assert len(expanded) == 1
    assert expanded[0].local == f1


@pytest.mark.asyncio
async def test_expand_upload_entries_empty_dir(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    entry = transfers.TransferEntry(local=empty_dir, remote="remote/empty", is_dir=True)

    class FakeArt:
        def __init__(self, path, auth=None):
            pass

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return []

        def relative_to(self, other):
            return Path()

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)
    expanded = await transfers.expand_upload_entries([entry])
    assert expanded == []


@pytest.mark.asyncio
async def test_expand_upload_entries_ignores_dead_symlinks(tmp_path, monkeypatch):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.txt").write_text("content")
    dead_symlink = folder / "broken"
    dead_symlink.symlink_to("/non/existent/target")

    class FakeArt:
        def __init__(self, path, auth=None):
            pass

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return [folder / "file.txt", dead_symlink]

        def relative_to(self, other):
            return Path((folder / "file.txt").name)

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)
    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)
    expanded = await transfers.expand_upload_entries([entry])
    assert len(expanded) == 1
    assert expanded[0].local.name == "file.txt"


@pytest.mark.asyncio
async def test_expand_upload_entries_skips_dead_symlink_file(tmp_path):
    dead_file = tmp_path / "broken.txt"
    dead_file.symlink_to("/non/existent/target")
    entry = transfers.TransferEntry(local=dead_file, remote="remote/broken.txt", is_dir=False)
    expanded = await transfers.expand_upload_entries([entry])
    assert expanded == []


@pytest.mark.asyncio
async def test_upload_end_to_end(tmp_path, monkeypatch):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file1.txt").write_text("abc")
    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)
    events = []

    class FakeArt:
        def __init__(self, path, auth=None):
            self.path = Path(path)

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return [folder / "file1.txt"]

        def relative_to(self, other):
            return Path("file1.txt")

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_session.put.return_value = fake_response
    monkeypatch.setattr(transfers, "create_session", lambda: fake_session)
    await transfers.upload([entry], progress_callback=lambda e, v: events.append((e, v)))
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_upload_skips_dead_symlink(tmp_path, monkeypatch):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.txt").write_text("hello")
    broken = folder / "broken"
    broken.symlink_to("/nonexistent")

    class FakeArt:
        def __init__(self, path, auth=None):
            pass

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return [folder / "file.txt", broken]

        def relative_to(self, other):
            return Path((folder / "file.txt").name)

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)
    fake_session = MagicMock()
    fake_response = MagicMock()
    fake_response.raise_for_status = lambda: None
    fake_session.put.return_value = fake_response
    monkeypatch.setattr(transfers, "create_session", lambda: fake_session)
    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)
    events = []
    await transfers.upload([entry], progress_callback=lambda ev, val: events.append((ev, val)))
    fake_session.put.assert_called_once()
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_upload_file_limited_cancel(monkeypatch, tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(local=file_path, remote="remote/file.txt", is_dir=False)
    monkeypatch.setattr(
        transfers,
        "create_session",
        lambda: MagicMock(put=lambda *a, **k: MagicMock(raise_for_status=lambda: None)),
    )
    cancel_event = asyncio.Event()
    cancel_event.set()
    semaphore = asyncio.Semaphore(4)
    await transfers.upload_file_limited(
        entry, transfers.create_session(), semaphore, cancel_event=cancel_event
    )


@pytest.mark.asyncio
async def test_upload_cancelled_error_handled(monkeypatch, tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    file_path = folder / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)

    class FakeArt:
        def __init__(self, path, auth=None):
            self.path = Path(path)

        def __truediv__(self, other):
            return self

        def rglob(self, pattern):
            return [file_path]

        def relative_to(self, other):
            return Path(file_path.name)

    monkeypatch.setattr(transfers, "ArtifactoryPath", FakeArt)

    class DummySession:
        def put(self, *a, **k):
            raise asyncio.CancelledError()

    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())
    await transfers.upload([entry])


def _make_dummy_get_session(chunks=(b"abc",)):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size):
            yield from chunks

        def raise_for_status(self):
            pass

    class DummySession:
        def get(self, url, stream=True, auth=None):
            return Resp()

    return DummySession()


def test_download_file_creates_parent(tmp_path):
    local_file = tmp_path / "nested" / "file.txt"
    entry = transfers.TransferEntry(local=local_file, remote="http://fake/file.txt", is_dir=False)
    transfers.download_file(entry, _make_dummy_get_session())
    assert local_file.exists()


def test_download_file_mid_read_cancel(tmp_path):
    local_file = tmp_path / "file.txt"
    entry = transfers.TransferEntry(local=local_file, remote="http://fake/file.txt", is_dir=False)

    cancel_event = asyncio.Event()
    call_count = 0

    def progress(event, val):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            cancel_event.set()

    with pytest.raises(asyncio.CancelledError):
        transfers.download_file(
            entry,
            _make_dummy_get_session(chunks=(b"abc", b"def")),
            progress_callback=progress,
            cancel_event=cancel_event,
        )


def _make_aql_session(results):
    session = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"results": results}
    resp.raise_for_status = MagicMock()
    session.post.return_value = resp
    # HEAD for single-file size
    head_resp = MagicMock()
    head_resp.headers = {"Content-Length": "0"}
    session.head.return_value = head_resp
    return session


def test_aql_expand_entry_single_file(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)  # reset cache
    results = [{"repo": "my-repo", "path": "a/b", "name": "file.txt", "size": 1234}]
    session = _make_aql_session(results)
    entry = transfers.TransferEntry(
        local=tmp_path / "folder",
        remote="https://srv/artifactory/my-repo/a/b/folder",
        is_dir=True,
    )
    expanded, total = transfers._aql_expand_entry(entry, "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert expanded[0].size == 1234
    assert total == 1234
    assert expanded[0].local.name == "file.txt"


def test_aql_expand_entry_root_path(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)  # reset cache
    results = [{"repo": "repo", "path": ".", "name": "root.txt", "size": 42}]
    session = _make_aql_session(results)
    entry = transfers.TransferEntry(
        local=tmp_path,
        remote="https://srv/artifactory/repo",
        is_dir=True,
    )
    expanded, total = transfers._aql_expand_entry(entry, "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert total == 42


def test_aql_expand_entry_fallback_on_error(tmp_path, monkeypatch):
    session = MagicMock()
    session.post.side_effect = Exception("AQL unavailable")

    dummy_entry = transfers.TransferEntry(
        local=tmp_path / "f.txt", remote="r", is_dir=False, size=99
    )
    monkeypatch.setattr(transfers, "_rglob_expand_entry", lambda *a, **k: ([dummy_entry], 99))

    entry = transfers.TransferEntry(
        local=tmp_path,
        remote="https://srv/artifactory/repo/path",
        is_dir=True,
    )
    expanded, total = transfers._aql_expand_entry(entry, "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert total == 99


def test_rglob_expand_entry(tmp_path, monkeypatch):
    class FakeChild:
        def __init__(self, name, size=50):
            self._name = name
            self._size = size

        def is_dir(self):
            return False

        def relative_to(self, root):
            return Path(self._name)

        def stat(self):
            return MagicMock(st_size=self._size)

        def __str__(self):
            return f"https://fake/{self._name}"

    class FakeRoot:
        def rglob(self, pattern):
            return [FakeChild("a.txt", 50), FakeChild("b.txt", 100)]

        def __truediv__(self, other):
            return self

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: FakeRoot())
    entry = transfers.TransferEntry(
        local=tmp_path / "local", remote="https://fake/repo", is_dir=True
    )
    expanded, total = transfers._rglob_expand_entry(entry, auth=None)
    assert len(expanded) == 2
    assert total == 150


def test_rglob_expand_entry_dir_children(tmp_path, monkeypatch):
    class FakeDir:
        def is_dir(self):
            return True

        def relative_to(self, root):
            return Path("subdir")

        def stat(self):
            return MagicMock(st_size=0)

    class FakeRoot:
        def rglob(self, pattern):
            return [FakeDir()]

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: FakeRoot())
    entry = transfers.TransferEntry(
        local=tmp_path / "local", remote="https://fake/repo", is_dir=True
    )
    expanded, total = transfers._rglob_expand_entry(entry, auth=None)
    assert expanded == []
    assert total == 0


def test_rglob_expand_entry_stat_exception(tmp_path, monkeypatch):
    class FakeChild:
        def is_dir(self):
            return False

        def relative_to(self, root):
            return Path("file.txt")

        def stat(self):
            raise OSError("permission denied")

        def __str__(self):
            return "https://fake/file.txt"

    class FakeRoot:
        def rglob(self, pattern):
            return [FakeChild()]

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: FakeRoot())
    entry = transfers.TransferEntry(
        local=tmp_path / "local", remote="https://fake/repo", is_dir=True
    )
    expanded, total = transfers._rglob_expand_entry(entry, auth=None)
    assert len(expanded) == 1
    assert expanded[0].size == 0
    assert total == 0


@pytest.mark.asyncio
async def test_expand_entries_single_file_head(tmp_path):
    session = MagicMock()
    head_resp = MagicMock()
    head_resp.headers = {"Content-Length": "512"}
    session.head.return_value = head_resp

    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt",
        remote="https://srv/artifactory/repo/file.txt",
        is_dir=False,
    )
    expanded, total = await transfers.expand_entries([entry], "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert total == 512
    session.post.assert_not_called()


@pytest.mark.asyncio
async def test_expand_entries_single_file_head_fails(tmp_path):
    session = MagicMock()
    session.head.side_effect = Exception("network error")

    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt",
        remote="https://srv/artifactory/repo/file.txt",
        is_dir=False,
    )
    expanded, total = await transfers.expand_entries([entry], "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert total == 0


@pytest.mark.asyncio
async def test_expand_entries_directory_uses_aql(tmp_path, monkeypatch):
    dummy_entry = transfers.TransferEntry(
        local=tmp_path / "f.txt", remote="r", is_dir=False, size=77
    )
    monkeypatch.setattr(transfers, "_aql_expand_entry", lambda *a, **k: ([dummy_entry], 77))

    session = MagicMock()
    entry = transfers.TransferEntry(
        local=tmp_path / "dir",
        remote="https://srv/artifactory/repo/dir",
        is_dir=True,
    )
    expanded, total = await transfers.expand_entries([entry], "https://srv", session, auth=None)
    assert len(expanded) == 1
    assert total == 77


@pytest.mark.asyncio
async def test_expand_entries_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_expand_entry", lambda *a, **k: ([], 0))
    session = MagicMock()
    entry = transfers.TransferEntry(
        local=tmp_path / "empty",
        remote="https://srv/artifactory/repo/empty",
        is_dir=True,
    )
    expanded, total = await transfers.expand_entries([entry], "https://srv", session, auth=None)
    assert expanded == []
    assert total == 0


@pytest.mark.asyncio
async def test_download_single_file_end_to_end(tmp_path, monkeypatch):
    local_file = tmp_path / "file.txt"
    entry = transfers.TransferEntry(
        local=local_file, remote="https://srv/artifactory/repo/file.txt", is_dir=False
    )
    events = []
    session = _make_dummy_get_session(chunks=(b"hello",))
    head_mock = MagicMock()
    head_mock.headers = {"Content-Length": "5"}
    session_mock = MagicMock()
    session_mock.head.return_value = head_mock
    session_mock.get = session.get

    monkeypatch.setattr(transfers, "create_session", lambda: session_mock)
    await transfers.download(
        [entry],
        base_url="https://srv",
        progress_callback=lambda e, v: events.append((e, v)),
    )
    assert local_file.exists()
    assert events[0] == ("start", 5)
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_download_cancel_triggers_finish(tmp_path, monkeypatch):
    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt",
        remote="https://srv/artifactory/repo/file.txt",
        is_dir=False,
    )
    session_mock = MagicMock()
    head_resp = MagicMock()
    head_resp.headers = {"Content-Length": "0"}
    session_mock.head.return_value = head_resp
    session_mock.get = _make_dummy_get_session().get

    monkeypatch.setattr(transfers, "create_session", lambda: session_mock)
    events = []
    cancel_event = asyncio.Event()
    cancel_event.set()

    await transfers.download(
        [entry],
        base_url="https://srv",
        progress_callback=lambda e, v: events.append((e, v)),
        cancel_event=cancel_event,
    )
    assert any(e[0] == "start" for e in events)
    assert any(e[0] == "finish" for e in events)


@pytest.mark.asyncio
async def test_download_file_limited_cancel(tmp_path):
    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt",
        remote="https://srv/artifactory/repo/file.txt",
        is_dir=False,
    )
    cancel_event = asyncio.Event()
    cancel_event.set()
    semaphore = asyncio.Semaphore(4)
    with pytest.raises(asyncio.CancelledError):
        await transfers.download_file_limited(
            entry,
            _make_dummy_get_session(),
            semaphore,
            cancel_event=cancel_event,
        )


@pytest.mark.asyncio
async def test_download_file_mid_cancel_via_limited(tmp_path):
    local_file = tmp_path / "file.txt"
    entry = transfers.TransferEntry(
        local=local_file, remote="https://srv/artifactory/repo/file.txt", is_dir=False
    )
    cancel_event = asyncio.Event()
    cancel_event.set()
    semaphore = asyncio.Semaphore(4)
    with pytest.raises(asyncio.CancelledError):
        await transfers.download_file_limited(
            entry,
            _make_dummy_get_session(chunks=(b"a" * 1024, b"b" * 1024)),
            semaphore,
            cancel_event=cancel_event,
        )


def test_aql_fallback_calls_warn_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)  # reset cache
    session = MagicMock()
    session.post.side_effect = Exception("403 Forbidden")

    warnings = []
    dummy_entry = transfers.TransferEntry(
        local=tmp_path / "f.txt", remote="r", is_dir=False, size=0
    )
    monkeypatch.setattr(transfers, "_rglob_expand_entry", lambda *a, **k: ([dummy_entry], 0))

    entry = transfers.TransferEntry(
        local=tmp_path,
        remote="https://srv/artifactory/repo/path",
        is_dir=True,
    )
    transfers._aql_expand_entry(
        entry,
        "https://srv",
        session,
        auth=None,
        warn_callback=lambda msg: warnings.append(msg),
    )

    assert len(warnings) == 1
    assert "AQL" in warnings[0]
    assert "fallback" in warnings[0].lower() or "walk" in warnings[0].lower()


def test_aql_warn_fires_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)  # reset cache
    session = MagicMock()
    session.post.side_effect = Exception("404 Not Found")

    warnings = []
    dummy_entry = transfers.TransferEntry(
        local=tmp_path / "f.txt", remote="r", is_dir=False, size=0
    )
    monkeypatch.setattr(transfers, "_rglob_expand_entry", lambda *a, **k: ([dummy_entry], 0))

    entry = transfers.TransferEntry(
        local=tmp_path,
        remote="https://srv/artifactory/repo/path",
        is_dir=True,
    )

    def cb(msg):
        warnings.append(msg)

    transfers._aql_expand_entry(entry, "https://srv", session, auth=None, warn_callback=cb)
    assert len(warnings) == 1

    transfers._aql_expand_entry(entry, "https://srv", session, auth=None, warn_callback=cb)
    assert len(warnings) == 1
    assert session.post.call_count == 1


def test_aql_no_warn_when_already_known_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", False)
    session = MagicMock()
    warnings = []
    dummy_entry = transfers.TransferEntry(
        local=tmp_path / "f.txt", remote="r", is_dir=False, size=0
    )
    monkeypatch.setattr(transfers, "_rglob_expand_entry", lambda *a, **k: ([dummy_entry], 0))

    entry = transfers.TransferEntry(
        local=tmp_path,
        remote="https://srv/artifactory/repo/path",
        is_dir=True,
    )
    transfers._aql_expand_entry(
        entry,
        "https://srv",
        session,
        auth=None,
        warn_callback=lambda msg: warnings.append(msg),
    )

    assert warnings == []
    session.post.assert_not_called()


def test_aql_no_warn_callback_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)  # reset cache
    results = [{"repo": "r", "path": "p", "name": "f.txt", "size": 10}]
    session = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"results": results}
    resp.raise_for_status = MagicMock()
    session.post.return_value = resp

    warnings = []
    entry = transfers.TransferEntry(
        local=tmp_path / "folder",
        remote="https://srv/artifactory/repo/p/folder",
        is_dir=True,
    )
    transfers._aql_expand_entry(
        entry,
        "https://srv",
        session,
        auth=None,
        warn_callback=lambda msg: warnings.append(msg),
    )
    assert warnings == []


@pytest.mark.asyncio
async def test_download_passes_warn_callback(tmp_path, monkeypatch):
    warnings = []

    async def fake_expand(entries, base_url, session, auth, warn_callback=None):
        if warn_callback:
            warn_callback("test warning")
        return [], 0

    monkeypatch.setattr(transfers, "expand_entries", fake_expand)
    monkeypatch.setattr(transfers, "create_session", lambda: MagicMock())

    await transfers.download(
        [],
        base_url="https://srv",
        warn_callback=lambda msg: warnings.append(msg),
    )
    assert warnings == ["test warning"]


@pytest.mark.asyncio
async def test_download_use_aql_false_skips_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(transfers, "_aql_available", None)

    expanded_entry = transfers.TransferEntry(
        local=tmp_path / "file.txt",
        remote="https://srv/artifactory/repo/file.txt",
        is_dir=False,
    )
    session_mock = MagicMock()
    head_resp = MagicMock()
    head_resp.headers = {"Content-Length": "10"}
    session_mock.head.return_value = head_resp
    session_mock.get = _make_dummy_get_session(chunks=(b"hello",)).get
    monkeypatch.setattr(transfers, "create_session", lambda: session_mock)

    await transfers.download(
        [expanded_entry],
        base_url="https://srv",
        use_aql=False,
    )

    assert transfers._aql_available is False
    session_mock.post.assert_not_called()
