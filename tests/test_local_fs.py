import asyncio
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest  # type: ignore

from arty_mc.core import local_fs
from arty_mc.core.local_fs import MAX_CONCURRENCY, LocalFS  # type: ignore


def test_max_concurrency_constant():
    assert MAX_CONCURRENCY == 4


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


@pytest.mark.asyncio
async def test_cd_and_up(tmp_path):
    fs = local_fs.LocalFS()
    fs.cd(str(tmp_path))
    assert fs.cwd.endswith(str(tmp_path))
    fs.up()
    expected = str(Path(tmp_path).parent)
    assert fs.cwd == expected
    fs.up()
    expected2 = str(Path(expected).parent)
    assert fs.cwd == expected2


def test_path_helper(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    p = fs.path("file.txt")
    assert p == os.path.join(fs.cwd, "file.txt")


def test_list_handles_stat_none(monkeypatch):
    fs = LocalFS()
    fake = MagicMock()
    fake.name = "file"
    fake.path = "file"
    fake.is_symlink.return_value = False
    fake.is_dir.return_value = False
    fake.stat.return_value = None
    monkeypatch.setattr("os.scandir", lambda _: [fake])
    items = fs.list()
    assert items[0]["size"] == 0
    assert items[0]["modified"] is None


def test_list_stat_exception(monkeypatch):
    fs = LocalFS()
    fake = MagicMock()
    fake.name = "file"
    fake.path = "file"
    fake.is_symlink.return_value = False
    fake.is_dir.side_effect = Exception("boom")
    fake.stat.side_effect = Exception("boom")
    monkeypatch.setattr("os.scandir", lambda _: [fake])
    items = fs.list()
    assert items[0]["size"] == 0
    assert items[0]["modified"] is None
    assert items[0]["is_dir"] is False


@pytest.mark.asyncio
async def test_delete_nonexistent(tmp_path):
    fs = local_fs.LocalFS()
    fs.cwd = str(tmp_path)
    called = []

    await fs.delete("doesnotexist", progress_callback=lambda e, v: called.append(e))
    # Should not fail, callback not called
    assert called == []


@pytest.mark.asyncio
async def test_delete_file(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("abc")

    fs = local_fs.LocalFS()
    fs.cwd = str(tmp_path)
    called_events = []

    def progress(event, val):
        called_events.append((event, val))

    await fs.delete("file.txt", progress_callback=progress)
    assert not file_path.exists()
    assert called_events[0][0] == "start"
    assert called_events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_delete_directory(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "file.txt").write_text("abc")

    fs = local_fs.LocalFS()
    fs.cwd = str(tmp_path)
    events = []

    await fs.delete("folder", progress_callback=lambda e, v: events.append((e, v)))
    assert not folder.exists()
    assert events[0][0] == "start"
    assert events[-1][0] == "finish"


@pytest.mark.asyncio
async def test_delete_directory_with_progress(tmp_path, monkeypatch):
    d = tmp_path / "dir"
    d.mkdir()
    (d / "a.txt").write_text("a")
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    events = []

    def progress(evt, val):
        events.append(evt)

    await fs.delete("dir", progress_callback=progress)
    assert not d.exists()
    assert "advance" in events


@pytest.mark.asyncio
async def test_delete_with_cancel_event(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("data")
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    cancel_event = asyncio.Event()
    await fs.delete("file.txt", cancel_event=cancel_event)
    assert not f.exists()


@pytest.mark.asyncio
async def test_delete_exception(monkeypatch, tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("data")
    monkeypatch.chdir(tmp_path)

    def boom(*args, **kwargs):
        raise OSError("cannot delete")

    monkeypatch.setattr("os.remove", boom)
    fs = LocalFS()
    await fs.delete("file.txt")


@pytest.mark.asyncio
async def test_list_dead_symlink(tmp_path):
    # Create a dead symlink
    dead_link = tmp_path / "broken.txt"
    dead_link.symlink_to("/non/existent/target")

    fs = local_fs.LocalFS()
    fs.cwd = str(tmp_path)

    items = fs.list()
    dead_entry = next((f for f in items if f["name"] == "broken.txt"), None)

    assert dead_entry is not None
    assert dead_entry["is_dead_symlink"] is True
    assert dead_entry["is_dir"] is False
    assert dead_entry["is_empty_dir"] is False


@pytest.mark.asyncio
async def test_list_empty_dir(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    def fake_listdir(path):
        raise PermissionError("test")

    monkeypatch.setattr("os.listdir", fake_listdir)

    fs = local_fs.LocalFS()
    fs.cwd = str(tmp_path)
    items = fs.list()
    empty_entry = next((f for f in items if f["name"] == "empty"), None)

    assert empty_entry is not None
    assert empty_entry["is_dir"] is True
    assert empty_entry["is_empty_dir"] is False


@pytest.mark.asyncio
async def test_list_symlink(tmp_path):
    fs = local_fs.LocalFS()
    target_file = tmp_path / "target.txt"
    target_file.write_text("hello")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(target_file)
    fs.cd(str(tmp_path))
    items = fs.list()
    link_entry = next((i for i in items if i["name"] == "link.txt"), None)
    assert link_entry is not None
    assert link_entry["is_dead_symlink"] is False
    assert link_entry["is_dir"] is False
    assert link_entry["size"] == target_file.stat().st_size

    expected_modified = datetime.fromtimestamp(target_file.stat().st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    assert link_entry["modified"] == expected_modified
