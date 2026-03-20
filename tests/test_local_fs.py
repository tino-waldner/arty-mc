import asyncio
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest  # type: ignore

from arty_mc.core.fs_utils import is_accessible, is_copyable
from arty_mc.core.local_fs import MAX_CONCURRENCY, LocalFS


def test_max_concurrency_constant():
    assert MAX_CONCURRENCY == 4


def test_file_entry_construction():
    from arty_mc.core.local_fs import FileEntry

    fe = FileEntry(path="/some/dir/file.txt", is_dir=False)
    assert fe.path == "/some/dir/file.txt"
    assert fe.is_dir is False
    assert fe.name == "file.txt"

    fe_dir = FileEntry(path="/some/dir/", is_dir=True)
    assert fe_dir.is_dir is True
    assert fe_dir.name == "dir"


def test_is_accessible_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("abc")
    assert is_accessible(f) is True


def test_is_accessible_dir(tmp_path):
    d = tmp_path / "dir"
    d.mkdir()
    assert is_accessible(d) is True


def test_is_accessible_dead_symlink(tmp_path):
    link = tmp_path / "broken"
    link.symlink_to("/non/existent/target")
    assert is_accessible(link) is False


def test_is_accessible_no_permission(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("abc")
    monkeypatch.setattr(os, "access", lambda path, mode: False)
    assert is_accessible(f) is False


def test_is_accessible_stat_exception(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    with patch("os.stat", side_effect=OSError("boom")):
        assert is_accessible(f) is False


def test_is_accessible_special_file(tmp_path):
    f = tmp_path / "weirdfile"
    f.write_text("data")
    with (
        patch("os.path.realpath", lambda p: str(f)),
        patch("os.stat", return_value=MagicMock(st_mode=0o777)),
        patch("stat.S_ISDIR", return_value=False),
        patch("stat.S_ISREG", return_value=False),
    ):
        assert is_accessible(f) is False


def test_is_copyable_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    assert is_copyable(f) is True


def test_is_copyable_nonempty_dir(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "x").write_text("x")
    assert is_copyable(d) is True


def test_is_copyable_empty_dir(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert is_copyable(d) is False


def test_is_copyable_inaccessible(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("abc")
    with patch("arty_mc.core.fs_utils.is_accessible", return_value=False):
        assert is_copyable(f) is False


def test_is_copyable_listdir_exception(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "x").write_text("x")
    with patch("os.listdir", side_effect=PermissionError()):
        assert is_copyable(d) is False


def test_list_files_and_dirs(tmp_path, monkeypatch):
    (tmp_path / "b.txt").write_text("hello")
    (tmp_path / "a").mkdir()
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    items = fs.list()
    assert items[0]["is_dir"] is True
    assert items[0]["name"] == "a"
    assert items[1]["is_dir"] is False
    assert items[1]["name"] == "b.txt"


def test_list_dead_symlink(tmp_path):
    dead_link = tmp_path / "broken.txt"
    dead_link.symlink_to("/non/existent/target")
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    entry = next(f for f in items if f["name"] == "broken.txt")
    assert entry["is_dead_symlink"] is True
    assert entry["is_dir"] is False
    assert entry["is_unreadable"] is True


def test_list_empty_dir(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    entry = next(f for f in items if f["name"] == "empty")
    assert entry["is_dir"] is True
    assert entry["is_empty_dir"] is True


def test_list_unreadable_dir(tmp_path, monkeypatch):
    d = tmp_path / "secret"
    d.mkdir()

    def fake_access(path, mode):
        return False if path == str(d) else True

    monkeypatch.setattr(os, "access", fake_access)
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    entry = next(f for f in items if f["name"] == "secret")
    assert entry["is_unreadable"] is True
    assert entry["is_dir"] is True


def test_list_unreadable_file(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("hello")

    def fake_access(path, mode):
        return not (path == str(f) and mode == os.R_OK)

    monkeypatch.setattr(os, "access", fake_access)
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    entry = next(x for x in items if x["name"] == "file.txt")
    assert entry["is_unreadable"] is True
    assert entry["is_dir"] is False


def test_list_special_file_unreadable(tmp_path):
    f = tmp_path / "weirdfile"
    f.write_text("data")
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    with (
        patch("os.path.realpath", lambda p: str(f)),
        patch("os.stat", return_value=MagicMock(st_mode=0o777)),
        patch("stat.S_ISDIR", return_value=False),
        patch("stat.S_ISREG", return_value=False),
    ):
        items = fs.list()
    entry = next((x for x in items if x["name"] == "weirdfile"), None)
    assert entry is not None
    assert entry["is_unreadable"] is True


def test_list_handles_stat_exception(monkeypatch):
    fs = LocalFS()
    fake = MagicMock()
    fake.name = "file"
    fake.path = "file"
    fake.stat.side_effect = Exception("boom")
    monkeypatch.setattr("os.scandir", lambda _: [fake])
    items = fs.list()
    assert items[0]["size"] == 0
    assert items[0]["is_unreadable"] is True


def test_list_handles_unreadable_via_stat(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("abc")
    monkeypatch.setattr(os, "stat", lambda path: (_ for _ in ()).throw(PermissionError()))
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    for item in items:
        assert item["is_unreadable"] is True


def test_list_symlink_to_file(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("hello")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    fs = LocalFS()
    fs.cd(str(tmp_path))
    items = fs.list()
    entry = next(i for i in items if i["name"] == "link.txt")
    assert entry["is_dead_symlink"] is False
    assert entry["is_dir"] is False
    assert entry["size"] == target.stat().st_size
    expected_modified = datetime.fromtimestamp(target.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    assert entry["modified"] == expected_modified


def test_list_listdir_exception_on_dir(tmp_path, monkeypatch):
    d = tmp_path / "dir"
    d.mkdir()
    monkeypatch.setattr(os, "listdir", lambda p: (_ for _ in ()).throw(PermissionError()))
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    entry = next(f for f in items if f["name"] == "dir")
    assert entry["is_dir"] is True
    assert entry["is_unreadable"] is True


def test_cd_success(tmp_path):
    fs = LocalFS()
    result = fs.cd(str(tmp_path))
    assert result is True
    assert fs.cwd == str(tmp_path)


def test_cd_inaccessible(tmp_path):
    fs = LocalFS()
    with patch.object(fs, "is_accessible_from_ui", return_value=False):
        pass
    with patch("arty_mc.core.local_fs.is_accessible", return_value=False):
        result = fs.cd(str(tmp_path))
    assert result is False


def test_up_success(tmp_path):
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    result = fs.up()
    assert result is True
    assert fs.cwd == str(Path(tmp_path).parent)


def test_up_inaccessible_parent(tmp_path):
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    with patch("arty_mc.core.local_fs.is_accessible", return_value=False):
        result = fs.up()
    assert result is False
    assert fs.cwd == str(tmp_path)


def test_up_at_filesystem_root():
    fs = LocalFS()
    fs.cwd = "/"
    result = fs.up()
    assert result is False
    assert fs.cwd == "/"


def test_path_helper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    assert fs.path("file.txt") == os.path.join(fs.cwd, "file.txt")


def test_is_accessible_from_ui_nonempty_dir(tmp_path):
    fs = LocalFS()
    d = tmp_path / "d"
    d.mkdir()
    (d / "a.txt").write_text("1")
    assert fs.is_accessible_from_ui(d) is True


def test_is_accessible_from_ui_empty_dir(tmp_path):
    fs = LocalFS()
    d = tmp_path / "empty"
    d.mkdir()
    assert fs.is_accessible_from_ui(d) is False


def test_is_accessible_from_ui_inaccessible(tmp_path):
    fs = LocalFS()
    path = tmp_path / "x"
    with patch("arty_mc.core.local_fs.is_accessible", return_value=False):
        assert fs.is_accessible_from_ui(path) is False


@pytest.mark.asyncio
async def test_delete_nonexistent(tmp_path):
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    called = []
    await fs.delete("doesnotexist", progress_callback=lambda e, v: called.append(e))
    assert called == []


@pytest.mark.asyncio
async def test_delete_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("abc")
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    events = []
    await fs.delete("file.txt", progress_callback=lambda e, v: events.append((e, v)))
    assert not f.exists()
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_delete_directory(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.txt").write_text("abc")
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    events = []
    await fs.delete("folder", progress_callback=lambda e, v: events.append((e, v)))
    assert not folder.exists()
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_delete_with_cancel_event(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    cancel_event = asyncio.Event()
    await fs.delete("file.txt", cancel_event=cancel_event)
    assert not f.exists()


@pytest.mark.asyncio
async def test_delete_exception(monkeypatch, tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    monkeypatch.setattr(
        os, "remove", lambda *a, **k: (_ for _ in ()).throw(OSError("cannot delete"))
    )
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    with pytest.raises(RuntimeError, match="cannot delete"):
        await fs.delete("file.txt")


@pytest.mark.asyncio
async def test_delete_item_progress_fires_on_error(monkeypatch, tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    monkeypatch.setattr(os, "remove", lambda *a, **k: (_ for _ in ()).throw(OSError("disk error")))
    fs = LocalFS()
    fs.cwd = str(tmp_path)
    events = []

    with pytest.raises(RuntimeError):
        fs._delete_item(str(f), progress_callback=lambda e, v: events.append(e))

    assert "advance" in events
