import asyncio
import os
from unittest.mock import MagicMock

import pytest  # type: ignore

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


def test_cd_and_up(tmp_path, monkeypatch):
    (tmp_path / "folder").mkdir()
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    fs.cd("folder")
    assert fs.cwd.endswith("folder")
    fs.up()
    assert fs.cwd == str(tmp_path)


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
async def test_delete_nonexistent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    await fs.delete("missing.txt")


@pytest.mark.asyncio
async def test_delete_file(tmp_path, monkeypatch):
    f = tmp_path / "file.txt"
    f.write_text("data")
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    events = []

    def progress(evt, val):
        events.append(evt)

    await fs.delete("file.txt", progress_callback=progress)
    assert not f.exists()
    assert "start" in events
    assert "advance" in events
    assert "finish" in events


@pytest.mark.asyncio
async def test_delete_directory(tmp_path, monkeypatch):
    d = tmp_path / "dir"
    d.mkdir()
    (d / "a.txt").write_text("a")
    monkeypatch.chdir(tmp_path)
    fs = LocalFS()
    await fs.delete("dir")
    assert not d.exists()


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
