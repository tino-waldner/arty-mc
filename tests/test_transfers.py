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


def test_progress_file_getattr(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("abc")
    pf = transfers.ProgressFile(file_path)
    assert hasattr(pf, "read")
    assert hasattr(pf, "close")
    assert hasattr(pf, "name") or hasattr(pf.file, "name")
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
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )
    dummy_session = MagicMock()
    dummy_response = MagicMock()
    dummy_response.raise_for_status = MagicMock()
    dummy_session.put.return_value = dummy_response
    transfers.upload_file(entry, dummy_session)
    dummy_session.put.assert_called_once()
    dummy_response.raise_for_status.assert_called_once()


def test_upload_file_raises(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )

    dummy_response = MagicMock()
    dummy_response.raise_for_status.side_effect = Exception("fail")
    dummy_session = MagicMock()
    dummy_session.put.return_value = dummy_response

    with pytest.raises(Exception):
        transfers.upload_file(entry, dummy_session)


@pytest.mark.asyncio
async def test_upload_end_to_end(tmp_path, monkeypatch):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file1.txt").write_text("abc")

    entry = transfers.TransferEntry(local=folder, remote="remote/folder", is_dir=True)
    events = []

    def cb(event, val):
        events.append((event, val))

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
    await transfers.upload([entry], progress_callback=cb)
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_upload_file_limited_cancel(monkeypatch, tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )

    monkeypatch.setattr(
        transfers,
        "create_session",
        lambda: MagicMock(put=lambda *a, **k: MagicMock(raise_for_status=lambda: None)),
    )

    cancel_event = asyncio.Event()
    cancel_event.set()
    await transfers.upload_file_limited(
        entry, transfers.create_session(), cancel_event=cancel_event
    )


@pytest.mark.asyncio
async def test_upload_file_early_cancel(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )
    cancel_event = asyncio.Event()
    cancel_event.set()  # trigger early exit

    await transfers.upload_file_limited(
        entry, transfers.create_session(), cancel_event=cancel_event
    )


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
async def test_download_file_creates_parent(monkeypatch, tmp_path):
    local_file = tmp_path / "nested" / "file.txt"
    entry = transfers.TransferEntry(
        local=local_file, remote="remote/file.txt", is_dir=False
    )

    class DummySession:
        def get(self, url, stream=True, auth=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def iter_content(self, chunk_size):
                    yield b"abc"

                def raise_for_status(self):
                    pass

            return Resp()

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: path)
    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())

    transfers.download_file(entry, DummySession())
    assert local_file.exists()


@pytest.mark.asyncio
async def test_download_total_bytes_exception(monkeypatch, tmp_path):
    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt", remote="remote/file.txt", is_dir=False
    )

    class DummyArt:
        def __init__(self, path, auth=None):
            pass

        def stat(self):
            raise Exception("fail")

    class DummySession:
        def get(self, url, stream=True, auth=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def iter_content(self, chunk_size):
                    yield b"abc"

                def raise_for_status(self):
                    pass

            return Resp()

    monkeypatch.setattr(transfers, "ArtifactoryPath", DummyArt)
    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())
    events = []

    def cb(event, val):
        events.append((event, val))

    await transfers.download([entry], progress_callback=cb)
    assert events[0][0] == "start"


@pytest.mark.asyncio
async def test_download_file_limited_cancel(monkeypatch, tmp_path):
    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt", remote="remote/file.txt", is_dir=False
    )

    class DummySession:
        def get(self, url, stream=True, auth=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def iter_content(self, chunk_size):
                    yield b"abc"

                def raise_for_status(self):
                    pass

            return Resp()

    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())
    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: path)
    cancel_event = asyncio.Event()
    cancel_event.set()
    with pytest.raises(asyncio.CancelledError):
        await transfers.download_file_limited(
            entry, DummySession(), cancel_event=cancel_event
        )


@pytest.mark.asyncio
async def test_download_cancel_triggers_finish(monkeypatch, tmp_path):
    entry = transfers.TransferEntry(
        local=tmp_path / "file.txt", remote="remote/file.txt", is_dir=False
    )

    class DummySession:
        def get(self, url, stream=True, auth=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def iter_content(self, chunk_size):
                    yield b"abc"

                def raise_for_status(self):
                    pass

            return Resp()

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: path)
    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())
    events = []
    cancel_event = asyncio.Event()
    cancel_event.set()  # immediately cancel

    await transfers.download(
        [entry],
        progress_callback=lambda e, v: events.append((e, v)),
        cancel_event=cancel_event,
    )

    assert any(e[0] == "start" for e in events)
    assert any(e[0] == "finish" for e in events)


@pytest.mark.asyncio
async def test_download_file_mid_cancel(tmp_path, monkeypatch):
    local_file = tmp_path / "file.txt"
    entry = transfers.TransferEntry(
        local=local_file, remote="remote/file.txt", is_dir=False
    )

    class DummySession:
        def get(self, url, stream=True, auth=None):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def iter_content(self, chunk_size):
                    yield b"a" * 1024
                    yield b"b" * 1024

                def raise_for_status(self):
                    pass

            return Resp()

    cancel_event = asyncio.Event()
    cancel_event.set()  # simulate cancel
    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())
    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: path)

    with pytest.raises(asyncio.CancelledError):
        await transfers.download_file_limited(
            entry, DummySession(), cancel_event=cancel_event
        )


def test_upload_file_early_cancel_direct(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )
    cancel_event = asyncio.Event()
    cancel_event.set()

    dummy_session = MagicMock()
    transfers.upload_file(entry, dummy_session, cancel_event=cancel_event)
    dummy_session.put.assert_not_called()


def test_download_file_mid_read_cancel(tmp_path, monkeypatch):
    local_file = tmp_path / "file.txt"
    entry = transfers.TransferEntry(
        local=local_file, remote="remote/file.txt", is_dir=False
    )

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size):
            yield b"abc"
            yield b"def"

        def raise_for_status(self):
            pass

    class DummySession:
        def get(self, url, stream=True, auth=None):
            return DummyResp()

    cancel_event = asyncio.Event()
    call_count = 0

    def progress(event, val):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            cancel_event.set()

    monkeypatch.setattr(transfers, "ArtifactoryPath", lambda path, auth=None: path)
    monkeypatch.setattr(transfers, "create_session", lambda: DummySession())

    with pytest.raises(asyncio.CancelledError):
        transfers.download_file(
            entry, DummySession(), progress_callback=progress, cancel_event=cancel_event
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


@pytest.mark.asyncio
async def test_expand_entries_dir_and_file(tmp_path, monkeypatch):
    local_root = tmp_path / "local"
    local_root.mkdir()
    remote_root = "remote_root"

    class DummyChild:
        def __init__(self, path, is_dir):
            self._path = Path(path)
            self._is_dir = is_dir

        def is_dir(self):
            return self._is_dir

        def relative_to(self, other):
            return Path(self._path.name)

    class DummyArt:
        def __init__(self, path, auth=None):
            pass

        def rglob(self, pattern):
            return [DummyChild("subdir", True), DummyChild("file.txt", False)]

        def __truediv__(self, other):
            return self

    monkeypatch.setattr(transfers, "ArtifactoryPath", DummyArt)
    entry = transfers.TransferEntry(local=local_root, remote=remote_root, is_dir=True)
    expanded = await transfers.expand_entries([entry], auth=None)
    assert len(expanded) == 1
    assert expanded[0].local.name == "file.txt"


@pytest.mark.asyncio
async def test_expand_upload_entries_with_file(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello")
    entry = transfers.TransferEntry(
        local=file_path, remote="remote/file.txt", is_dir=False
    )
    expanded = await transfers.expand_upload_entries([entry])
    assert len(expanded) == 1
    assert expanded[0].local == file_path
    assert expanded[0].remote == "remote/file.txt"
    assert not expanded[0].is_dir
