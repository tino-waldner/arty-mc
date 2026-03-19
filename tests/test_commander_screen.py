import asyncio
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest  # type: ignore

from arty_mc.core.artifactory_fs import FileEntry as ArtifactoryFileEntry
from arty_mc.ui.commander_screen import CommanderScreen


class DummyWorker:
    def __init__(self):
        self.wait = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def patch_transfers():
    """Stub out the actual upload/download coroutines so no network I/O occurs."""

    async def dummy_coro(*args, **kwargs):
        return None

    with (
        patch(
            "arty_mc.core.transfers.upload", side_effect=lambda *a, **k: dummy_coro()
        ),
        patch(
            "arty_mc.core.transfers.download", side_effect=lambda *a, **k: dummy_coro()
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def patch_textual_ui():
    with (
        patch("arty_mc.ui.commander_screen.TransferPanel", autospec=True) as mock_tp,
        patch("arty_mc.ui.commander_screen.DeletePanel", autospec=True) as mock_dp,
    ):
        mock_tp.return_value.remove = AsyncMock(return_value=None)
        mock_dp.return_value.remove = AsyncMock(return_value=None)
        yield mock_tp, mock_dp


@pytest.fixture
def fake_screen():
    dummy_config = {
        "server": "http://dummy",
        "user": "dummy_user",
        "token": "dummy_token",
        "default_repo": "dummy_repo",
    }
    screen = CommanderScreen(config=dummy_config)
    fake_item = {"name": "file.txt", "is_dir": False}

    screen.local_table = Mock()
    screen.remote_table = Mock()
    screen.local_table.selected = Mock(return_value=fake_item)
    screen.remote_table.selected = Mock(return_value=fake_item)
    screen.local_table.set_enabled = Mock()
    screen.remote_table.set_enabled = Mock()
    screen.local_filter = Mock(display=True)
    screen.remote_filter = Mock(display=True)

    screen.local_fs = Mock()
    screen.local_fs.path = Mock(side_effect=lambda name: f"/local/{name}")
    screen.local_fs.list = Mock(return_value=[fake_item])
    screen.local_fs.cwd = "/local"
    screen.local_fs.up = Mock(return_value=True)
    screen.local_fs.cd = Mock(return_value=True)
    screen.local_fs.is_accessible = Mock(return_value=True)
    screen.local_fs.is_accessible_from_ui = Mock(return_value=True)

    screen.remote_fs = Mock()
    screen.remote_fs.repo = "dummy_repo"
    screen.remote_fs.server = "http://dummy"
    screen.remote_fs.path = Mock(side_effect=lambda name: f"remote/{name}")
    screen.remote_fs.list = Mock(return_value=[fake_item])
    screen.remote_fs.path_str = "remote/path"
    screen.remote_fs.api = Mock()
    screen.remote_fs.api.session = Mock()
    screen.remote_fs.api.session.session = Mock()
    screen.remote_fs.api.session.session.auth = None

    screen.local_path_line = Mock()
    screen.remote_path_line = Mock()

    def run_worker_mock(coro):
        worker = DummyWorker()

        async def runner():
            try:
                await coro
            except Exception:
                pass

        asyncio.create_task(runner())
        return worker

    screen.run_worker = Mock(side_effect=run_worker_mock)
    screen.mount = Mock()
    screen.set_focus = Mock()
    screen.get_active = Mock(
        return_value=Mock(selected=Mock(return_value=fake_item), ancestors_with_self=[])
    )
    screen.cancel_event = Mock()
    return screen


@pytest.mark.asyncio
async def test_copy_local_to_remote(fake_screen):
    fake_screen.active = "local"
    await fake_screen._copy_worker()
    fake_screen.run_worker.assert_called()


@pytest.mark.asyncio
async def test_copy_remote_to_local(fake_screen):
    fake_screen.active = "remote"
    await fake_screen._copy_worker()
    fake_screen.run_worker.assert_called()


@pytest.mark.asyncio
async def test_copy_worker_no_selection(fake_screen):
    fake_screen.get_active.return_value.selected = Mock(return_value=None)
    await fake_screen._copy_worker()
    fake_screen.run_worker.assert_not_called()


@pytest.mark.asyncio
async def test_copy_worker_ui_always_unlocked_on_early_return(fake_screen):
    """UI must be re-enabled even when no item is selected (try/finally)."""
    fake_screen.get_active.return_value.selected = Mock(return_value=None)
    await fake_screen._copy_worker()
    fake_screen.local_table.set_enabled.assert_any_call(True)
    fake_screen.remote_table.set_enabled.assert_any_call(True)


@pytest.mark.asyncio
async def test_copy_worker_progress_coverage(fake_screen):
    fake_screen.active = "local"

    class FakeEntry:
        def __init__(self):
            self.name = "file.txt"
            self.is_dir = False
            self.local = Mock()
            self.local.stat.return_value = Mock(st_size=789012)

        def __getitem__(self, key):
            return {"name": self.name, "is_dir": self.is_dir}[key]

    fake_screen.get_active.return_value = Mock(selected=lambda: FakeEntry())
    fake_screen.local_fs.path = lambda name: f"/local/{name}"
    panel_instance = Mock()
    panel_instance.start = Mock()
    panel_instance.advance = Mock()
    panel_instance.finish = Mock()
    panel_instance.remove = AsyncMock()

    async def fake_upload(
        entries, auth=None, progress_callback=None, cancel_event=None
    ):
        if progress_callback:
            progress_callback("start", 789012)
            progress_callback("advance", 456)
            progress_callback("finish", None)

    with (
        patch("arty_mc.ui.commander_screen.TransferPanel", return_value=panel_instance),
        patch("arty_mc.ui.commander_screen.upload", side_effect=fake_upload),
        patch("arty_mc.ui.commander_screen.Path") as mock_path_class,
    ):
        mock_path_class.return_value = Mock(stat=lambda: Mock(st_size=789012))
        fake_screen.run_worker = lambda coro: type(
            "W", (), {"wait": lambda self: coro}
        )()
        await fake_screen._copy_worker()

    panel_instance.start.assert_called_once()
    panel_instance.advance.assert_called_once()
    panel_instance.finish.assert_called_once()


@pytest.mark.asyncio
async def test_delete_local(fake_screen):
    fake_screen.active = "local"
    entry = ArtifactoryFileEntry(repo="", name="file.txt", is_dir=False)
    await fake_screen._delete_worker(entry)
    fake_screen.run_worker.assert_called()


@pytest.mark.asyncio
async def test_delete_remote(fake_screen):
    fake_screen.active = "remote"
    entry = ArtifactoryFileEntry(repo="dummy_repo", name="file.txt", is_dir=False)
    await fake_screen._delete_worker(entry)
    fake_screen.run_worker.assert_called()


@pytest.mark.asyncio
async def test_delete_worker_progress_coverage(fake_screen):
    fake_screen.active = "local"
    entry = Mock(name="file.txt", is_dir=False)
    entry.name = "file.txt"
    panel_instance = Mock()
    panel_instance.start = Mock()
    panel_instance.increment_total = Mock()
    panel_instance.advance = Mock()
    panel_instance.finish = Mock()
    panel_instance.remove = AsyncMock()

    async def fake_delete(target, progress_callback=None, cancel_event=None):
        if progress_callback:
            progress_callback("start", 1)
            progress_callback("add_total", 2)
            progress_callback("advance", 3)
            progress_callback("finish", None)

    fake_screen.local_fs.delete = fake_delete

    with patch("arty_mc.ui.commander_screen.DeletePanel", return_value=panel_instance):
        fake_screen.run_worker = lambda coro: type(
            "W", (), {"wait": lambda self: coro}
        )()
        await fake_screen._delete_worker(entry)

    panel_instance.start.assert_called_once_with(1)
    panel_instance.increment_total.assert_called_once_with(2)
    panel_instance.advance.assert_called_once_with(3)
    panel_instance.finish.assert_called_once()


def test_action_up_local_success(fake_screen):
    fake_screen.active = "local"
    fake_screen.local_fs.up = Mock(return_value=True)
    fake_screen.refresh_local = Mock()
    fake_screen.action_up()
    fake_screen.local_fs.up.assert_called_once()
    fake_screen.refresh_local.assert_called_once()


def test_action_up_local_blocked(fake_screen):
    fake_screen.active = "local"
    fake_screen.local_fs.up = Mock(return_value=False)
    fake_screen.refresh_local = Mock()
    fake_screen.action_up()
    fake_screen.refresh_local.assert_not_called()


def test_action_up_remote(fake_screen):
    fake_screen.active = "remote"
    fake_screen.remote_fs.up = Mock()
    fake_screen.refresh_remote = Mock()
    fake_screen.action_up()
    fake_screen.remote_fs.up.assert_called_once()
    fake_screen.refresh_remote.assert_called_once()


def test_action_switch(fake_screen):
    fake_screen.active = "local"
    fake_screen.action_switch()
    assert fake_screen.active == "remote"
    fake_screen.action_switch()
    assert fake_screen.active == "local"


def test_action_refresh(fake_screen):
    fake_screen.refresh_local = Mock()
    fake_screen.refresh_remote = Mock()
    fake_screen.action_refresh()
    fake_screen.refresh_local.assert_called_once()
    fake_screen.refresh_remote.assert_called_once()


def test_action_quit_uses_app_exit(fake_screen):
    """action_quit must call self.app.exit(), NOT sys.exit()."""
    mock_app = Mock()
    type(fake_screen).app = PropertyMock(return_value=mock_app)
    fake_screen.action_quit()
    mock_app.exit.assert_called_once()


def test_action_copy_no_selection(fake_screen):
    fake_screen.get_active.return_value.selected = Mock(return_value=None)
    fake_screen.action_copy()  # should not raise


def test_action_copy_local_not_accessible(fake_screen):
    fake_screen.active = "local"
    fake_screen.local_fs.is_accessible_from_ui = Mock(return_value=False)
    fake_screen._copy_worker = AsyncMock()
    fake_screen.action_copy()
    fake_screen._copy_worker.assert_not_called()


@pytest.mark.asyncio
async def test_action_copy_confirm_yes_local(fake_screen):
    fake_screen.active = "local"
    fake_screen._copy_worker = AsyncMock()
    mock_app = Mock()
    mock_app.push_screen = lambda dialog, callback=None: callback(True)
    type(fake_screen).app = PropertyMock(return_value=mock_app)
    fake_screen.action_copy()
    fake_screen._copy_worker.assert_called()


@pytest.mark.asyncio
async def test_action_copy_remote_active_triggers_copy_worker(fake_screen):
    fake_screen.active = "remote"
    fake_screen._copy_worker = AsyncMock()
    mock_app = Mock()
    mock_app.push_screen = lambda dialog, callback=None: callback(True)
    type(fake_screen).app = PropertyMock(return_value=mock_app)
    fake_screen.action_copy()
    fake_screen._copy_worker.assert_called_once()


def test_action_delete_no_selection(fake_screen):
    fake_screen.get_active.return_value.selected = Mock(return_value=None)
    fake_screen.action_delete()  # should not raise


def test_action_delete_local_not_accessible(fake_screen):
    fake_screen.active = "local"
    fake_screen.local_fs.is_accessible_from_ui = Mock(return_value=False)
    fake_screen._delete_worker = AsyncMock()
    fake_screen.action_delete()
    fake_screen._delete_worker.assert_not_called()


@pytest.mark.asyncio
async def test_action_delete_confirm_yes(fake_screen):
    fake_screen.active = "local"
    fake_screen._delete_worker = AsyncMock()
    mock_app = Mock()
    mock_app.push_screen = lambda dialog, callback=None: callback(True)
    type(fake_screen).app = PropertyMock(return_value=mock_app)
    fake_screen.action_delete()
    fake_screen._delete_worker.assert_called()


@pytest.mark.asyncio
async def test_action_delete_remote_active_triggers_delete_worker(fake_screen):
    fake_screen.active = "remote"
    fake_screen._delete_worker = AsyncMock()
    mock_app = Mock()
    mock_app.push_screen = lambda dialog, callback=None: callback(True)
    type(fake_screen).app = PropertyMock(return_value=mock_app)
    fake_screen.action_delete()
    fake_screen._delete_worker.assert_called_once()


@pytest.mark.asyncio
async def test_action_cancel(fake_screen):
    worker = DummyWorker()
    fake_screen.worker = worker
    fake_screen.cancel_event = Mock()
    await fake_screen.action_cancel()
    fake_screen.cancel_event.set.assert_called_once()
    fake_screen.cancel_event.clear.assert_called_once()


@pytest.mark.asyncio
async def test_action_cancel_cancelled_error(fake_screen):
    worker = Mock()

    async def wait():
        raise asyncio.CancelledError()

    worker.wait = wait
    fake_screen.worker = worker
    fake_screen.cancel_event = Mock()
    await fake_screen.action_cancel()
    fake_screen.cancel_event.set.assert_called_once()
    fake_screen.cancel_event.clear.assert_called_once()
    assert fake_screen.worker is None


def test_row_selected_local_dir(fake_screen):
    fake_screen.active = "local"
    fake_screen.get_active = Mock(return_value=fake_screen.local_table)
    fake_screen.local_table.selected = Mock(
        return_value={"name": "dir", "is_dir": True}
    )
    fake_screen.local_fs.cd = Mock(return_value=True)
    fake_screen.refresh_local = Mock()
    fake_screen.on_data_table_row_selected(Mock())
    fake_screen.local_fs.cd.assert_called_once_with("dir")
    fake_screen.refresh_local.assert_called_once()


def test_row_selected_local_dir_cd_blocked(fake_screen):
    fake_screen.active = "local"
    fake_screen.get_active = Mock(return_value=fake_screen.local_table)
    fake_screen.local_table.selected = Mock(
        return_value={"name": "locked", "is_dir": True}
    )
    fake_screen.local_fs.cd = Mock(return_value=False)
    fake_screen.refresh_local = Mock()
    fake_screen.on_data_table_row_selected(Mock())
    fake_screen.refresh_local.assert_not_called()


def test_row_selected_remote_dir(fake_screen):
    fake_screen.active = "remote"
    fake_screen.get_active = Mock(return_value=fake_screen.remote_table)
    fake_screen.remote_table.selected = Mock(
        return_value={"name": "dir", "is_dir": True}
    )
    fake_screen.remote_fs.cd = Mock()
    fake_screen.refresh_remote = Mock()
    fake_screen.on_data_table_row_selected(Mock())
    fake_screen.remote_fs.cd.assert_called_once_with("dir")
    fake_screen.refresh_remote.assert_called_once()


def test_row_selected_no_item(fake_screen):
    fake_screen.get_active = Mock(return_value=fake_screen.local_table)
    fake_screen.local_table.selected = Mock(return_value=None)
    fake_screen.on_data_table_row_selected(Mock())  # should not raise


def test_row_selected_not_dir(fake_screen):
    fake_screen.get_active = Mock(return_value=fake_screen.local_table)
    fake_screen.local_table.selected = Mock(
        return_value={"name": "file.txt", "is_dir": False}
    )
    fake_screen.local_fs.cd = Mock()
    fake_screen.refresh_local = Mock()
    fake_screen.on_data_table_row_selected(Mock())
    fake_screen.local_fs.cd.assert_not_called()
    fake_screen.refresh_local.assert_not_called()


def test_filter_local(fake_screen):
    fake_screen.local_table.apply_filter = Mock()
    event = Mock(sender=fake_screen.local_filter, value="abc")
    fake_screen.on_filter_bar_changed(event)
    fake_screen.local_table.apply_filter.assert_called_once_with("abc")


def test_filter_remote(fake_screen):
    fake_screen.remote_table.apply_filter = Mock()
    event = Mock(sender=fake_screen.remote_filter, value="xyz")
    fake_screen.on_filter_bar_changed(event)
    fake_screen.remote_table.apply_filter.assert_called_once_with("xyz")


def test_get_active_real_tables():
    with patch("arty_mc.ui.commander_screen.ArtifactoryFS"):
        screen = CommanderScreen(config={})
        screen.local_table = "LOCAL"
        screen.remote_table = "REMOTE"
        screen.active = "local"
        assert screen.get_active() == "LOCAL"
        screen.active = "remote"
        assert screen.get_active() == "REMOTE"
