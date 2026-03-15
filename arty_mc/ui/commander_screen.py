import asyncio
import sys
from pathlib import Path

from textual import on  # type: ignore
from textual.containers import Horizontal, Vertical  # type: ignore
from textual.screen import Screen  # type: ignore
from textual.widgets import DataTable, Footer, Header  # type: ignore

from arty_mc.core.artifactory_fs import ArtifactoryFS, FileEntry
from arty_mc.core.local_fs import LocalFS
from arty_mc.core.transfers import TransferEntry, download, upload
from arty_mc.ui.confirm_dialog import ConfirmDialog
from arty_mc.ui.delete_panel import DeletePanel
from arty_mc.ui.file_table import FileTable
from arty_mc.ui.filter_bar import FilterBar
from arty_mc.ui.path_line import PathLine
from arty_mc.ui.transfer_panel import TransferPanel


class CommanderScreen(Screen):
    BINDINGS = [
        ("enter", "open", "Open"),
        ("backspace", "up", "Up"),
        ("tab", "switch", "Switch Pane"),
        ("f2", "cancel", "Cancel"),
        ("f4", "refresh", "Refresh"),
        ("f5", "copy", "Copy"),
        ("f8", "delete", "Delete"),
        ("f10", "quit", "Quit"),
    ]

    def __init__(self, config):
        super().__init__()
        self.local_fs = LocalFS()
        self.remote_fs = ArtifactoryFS(config)
        self.local_table = None
        self.remote_table = None
        self.local_filter = None
        self.remote_filter = None
        self.active = "local"
        self.worker = None
        self.cancel_event = asyncio.Event()

    def compose(self):
        yield Header()
        with Horizontal():
            with Vertical():
                self.local_filter = FilterBar(id="local-filter")
                self.local_path_line = PathLine(self.local_fs.cwd)
                self.local_table = FileTable()
                yield self.local_filter
                yield self.local_path_line
                yield self.local_table

            with Vertical():
                self.remote_filter = FilterBar(id="remote-filter")
                self.remote_path_line = PathLine(
                    f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
                )
                self.remote_table = FileTable()
                yield self.remote_filter
                yield self.remote_path_line
                yield self.remote_table
        yield Footer()

    def on_mount(self):
        self.set_focus(self.local_table)
        self.refresh_local()
        self.refresh_remote()

    def get_active(self):
        return self.local_table if self.active == "local" else self.remote_table

    def refresh_local(self):
        self.local_table.load(self.local_fs.list())

    def refresh_remote(self):
        self.remote_table.load(self.remote_fs.list())

    def action_up(self):
        if self.active == "local":
            self.local_fs.up()
            self.local_path_line.path = self.local_fs.cwd
            self.refresh_local()
        else:
            self.remote_fs.up()
            self.remote_path_line.path = (
                f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
            )
            self.refresh_remote()

    def action_switch(self):
        self.active = "remote" if self.active == "local" else "local"
        self.set_focus(self.get_active())

    def action_refresh(self):
        self.refresh_local()
        self.refresh_remote()

    def action_quit(self):
        sys.exit()

    async def _copy_worker(self):
        self.local_table.set_enabled(False)
        self.remote_table.set_enabled(False)
        self.local_filter.display = False
        self.remote_filter.display = False
        self.transfer_panel = TransferPanel()
        self.mount(self.transfer_panel)

        def progress_handler(action, value):
            if action == "start":
                self.transfer_panel.start(value)
            elif action == "advance":
                self.transfer_panel.advance(value)
            elif action == "finish":
                self.transfer_panel.finish()

        item = self.get_active().selected()
        if not item:
            return

        if self.active == "local":
            local_path = Path(self.local_fs.path(item["name"]))
            remote_path = f"{self.remote_fs.repo}/{self.remote_fs.path(item['name'])}"
            entry = TransferEntry(
                local=local_path,
                remote=f"{self.remote_fs.server}/{remote_path}",
                is_dir=item["is_dir"],
            )
            self.worker = self.run_worker(
                upload(
                    [entry],
                    auth=self.remote_fs.api.session.session.auth,
                    progress_callback=progress_handler,
                    cancel_event=self.cancel_event,
                )
            )
            await self.worker.wait()
            self.refresh_remote()
        else:
            remote_full_path = (
                f"{self.remote_fs.repo}/{self.remote_fs.path(item['name'])}"
            )
            local_path = Path(self.local_fs.path(item["name"]))
            entry = TransferEntry(
                local=local_path,
                remote=f"{self.remote_fs.server}/{remote_full_path}",
                is_dir=item["is_dir"],
            )
            self.worker = self.run_worker(
                download(
                    [entry],
                    auth=self.remote_fs.api.session.session.auth,
                    progress_callback=progress_handler,
                    cancel_event=self.cancel_event,
                )
            )
            await self.worker.wait()
            self.refresh_local()

        self.transfer_panel.remove()
        self.local_table.set_enabled(True)
        self.remote_table.set_enabled(True)
        self.local_filter.display = True
        self.remote_filter.display = True
        self.set_focus(self.get_active())

    def action_copy(self):
        item = self.get_active().selected()
        if not item:
            return

        src = (
            self.local_fs.path(item["name"])
            if self.active == "local"
            else f"{self.remote_fs.repo}/{self.remote_fs.path(item['name'])}"
        )
        dst = (
            f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
            if self.active == "local"
            else self.local_fs.cwd
        )

        def after_confirm(result):
            if result:
                asyncio.create_task(self._copy_worker())

        self.app.push_screen(
            ConfirmDialog(f"Transfer '{src}' → '{dst}'?"), callback=after_confirm
        )

    async def _delete_worker(self, entry: FileEntry):
        self.local_table.set_enabled(False)
        self.remote_table.set_enabled(False)
        self.local_filter.display = False
        self.remote_filter.display = False

        self.delete_panel = DeletePanel()
        self.mount(self.delete_panel)

        def progress_handler(action, value):
            if action == "start":
                self.delete_panel.start(value)
            elif action == "add_total":
                self.delete_panel.increment_total(value)
            elif action == "advance":
                self.delete_panel.advance(value)
            elif action == "finish":
                self.delete_panel.finish()

        fs = self.local_fs if self.active == "local" else self.remote_fs

        target = entry.name if self.active == "local" else entry

        self.worker = self.run_worker(
            fs.delete(
                target,
                progress_callback=progress_handler,
                cancel_event=self.cancel_event,
            )
        )
        await self.worker.wait()

        if self.active == "local":
            self.refresh_local()
        else:
            self.refresh_remote()

        self.delete_panel.remove()
        self.local_table.set_enabled(True)
        self.remote_table.set_enabled(True)
        self.local_filter.display = True
        self.remote_filter.display = True
        self.set_focus(self.get_active())

    def action_delete(self):
        item = self.get_active().selected()
        if not item:
            return
        entry = FileEntry(
            repo=self.remote_fs.repo if self.active == "remote" else "",
            name=item["name"],
            is_dir=item["is_dir"],
        )

        path_name = (
            f"{self.local_fs.cwd}/{entry.name}"
            if self.active == "local"
            else f"{self.remote_fs.repo}/{self.remote_fs.path(entry.name)}"
        )

        def after_confirm(result):
            if result:
                asyncio.create_task(self._delete_worker(entry))

        self.app.push_screen(
            ConfirmDialog(f"Delete '{path_name}'?"), callback=after_confirm
        )

    async def action_cancel(self):
        if self.worker:
            self.cancel_event.set()
            try:
                await self.worker.wait()
            except asyncio.CancelledError:
                pass
            finally:
                self.cancel_event.clear()
                self.worker = None

    @on(DataTable.RowSelected)
    def on_data_table_row_selected(self, event):
        table = self.get_active()
        item = table.selected()
        if not item or not item.get("is_dir"):
            return
        if table == self.local_table:
            self.local_fs.cd(item["name"])
            self.local_path_line.path = self.local_fs.cwd
            self.refresh_local()
        else:
            self.remote_fs.cd(item["name"])
            self.remote_path_line.path = (
                f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
            )
            self.refresh_remote()

    @on(FilterBar.Changed)
    def on_filter_bar_changed(self, event):
        if event.sender == self.local_filter:
            self.local_table.apply_filter(event.value)
        elif event.sender == self.remote_filter:
            self.remote_table.apply_filter(event.value)
