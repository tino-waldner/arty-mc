import sys
import asyncio
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header
from textual.widgets import DataTable
from textual import on

from ui.path_line import PathLine
from ui.file_table import FileTable
from ui.filter_bar import FilterBar
from ui.transfer_panel import TransferPanel
from ui.delete_panel import DeletePanel
from ui.confirm_dialog import ConfirmDialog

from core.local_fs import LocalFS
from core.artifactory_fs import ArtifactoryFS
from core.transfers import upload, download

class CommanderScreen(Screen):

    BINDINGS = [
        ("enter", "open", "Open"),
        ("backspace", "up", "Up"),
        ("tab", "switch", "Switch Pane"),
        ("f4", "refresh", "Refresh"),
        ("f5", "copy", "Copy"),
        ("f8", "delete", "Delete"),
        ("f10", "quit", "Quit"),
    ]

    def __init__(self, config):
        super().__init__()

        self.local_fs = LocalFS()
        self.remote_fs = ArtifactoryFS(config)
        self.local_filter = None
        self.remote_filter = None
        self.local_table = None
        self.remote_table = None
        self.active = "local"

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
                self.remote_path_line = PathLine(f"{self.remote_fs.repo}/{self.remote_fs.path_str}")
                self.remote_table = FileTable()

                yield self.remote_filter
                yield self.remote_path_line
                yield self.remote_table

        yield Footer()

    def on_mount(self):
        self.set_focus(self.local_table)

        self.refresh_local()
        self.refresh_remote()

        self.local_table.load(
            self.local_fs.list()
        )

        self.remote_table.load(
            self.remote_fs.list()
        )


    def refresh_local(self):
        self.local_table.load(
            self.local_fs.list()
        )

    def refresh_remote(self):
        self.remote_table.load(
            self.remote_fs.list()
        )

    def get_active(self):
        if self.active == "local":
            return self.local_table
        elif self.active == "remote":
            return self.remote_table
        return None

    def action_up(self):
        if self.active == "local":
            self.local_fs.up()
            self.local_path_line.path = self.local_fs.cwd
            self.refresh_local()

        else:
            self.remote_fs.up()
            self.remote_path_line.path = f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
            self.refresh_remote()


    async def _delete_worker(self, name):

       self.delete_panel = DeletePanel()
       self.mount(self.delete_panel)

       table = self.get_active()
       item = table.selected()

       def progress_handler(action, value):
           if action == "start":
               self.delete_panel.start(value)
           elif action == "advance":
               self.delete_panel.advance()
           elif action == "finish":
               self.delete_panel.finish()
               self.delete_panel.remove()
    
       if self.active == "local":
           worker = self.run_worker(self.local_fs.delete(item["name"], 
               progress_callback=progress_handler))

           result = await worker.wait()
           self.refresh_local()

       elif self.active == "remote":
           worker = self.run_worker(self.remote_fs.delete(item["name"],
               progress_callback=progress_handler))

           result = await worker.wait()
           self.refresh_remote()


    def action_delete(self):
        table = self.get_active()
        item = table.selected()
        if not item:
            return

        name = item["name"]

        if self.active == "local":
            path = self.local_fs.cwd
            path_name = f"{path}/{name}"

        if self.active == "remote":
            repo = self.remote_fs.repo
            path = self.remote_fs.path(name)
            path_name = f"{repo}/{path}"


        def after_confirm(result):
            if not result:
                return
            asyncio.create_task(self._delete_worker(name))

        self.app.push_screen(
                ConfirmDialog(f"Delete '{path_name}'?"),
                callback=after_confirm
        )
            

    async def _copy_worker(self):
        self.transfer_panel = TransferPanel()
        self.mount(self.transfer_panel)

        def progress_handler(action, value):
            if action == "start":
                self.transfer_panel.start(value)
            elif action == "advance":
                self.transfer_panel.advance()
            elif action == "finish":
                self.transfer_panel.finish()
                self.transfer_panel.remove()

        if self.active == "local":
            item = self.local_table.selected()

            if not item:
                return

            src = self.local_fs.path(item["name"])
            dst = self.remote_fs.path_str

            worker = self.run_worker(upload(
                local_path=src,
                remote_path=dst,
                remote_repo_url=self.remote_fs.server + "/" + self.remote_fs.repo,
                auth=self.remote_fs.api.session.session.auth,
                progress_callback=progress_handler)
            )

            result = await worker.wait()
            self.refresh_remote()

        elif self.active == "remote":
            item = self.remote_table.selected()

            if not item:
                 return

            src = self.remote_fs.path(item["name"])
            dst = self.local_fs.path(item["name"])

            worker = self.run_worker(download(
                 remote_path=src,
                 local_path=dst,
                 remote_repo_url=self.remote_fs.server + "/" + self.remote_fs.repo,
                 auth=self.remote_fs.api.session.session.auth,
                 progress_callback=progress_handler)
            )

            result = await worker.wait()
            self.refresh_local()

    def action_copy(self):
        if self.active == "local":
            item = self.local_table.selected()

            if not item:
                return

            src = self.local_fs.path(item["name"])
            dst = f"{self.remote_fs.repo}/{self.remote_fs.path_str}"

        elif self.active == "remote":
            item = self.remote_table.selected()

            if not item:
                 return

            remote_name=self.remote_fs.path(item["name"])
            src = f"{self.remote_fs.repo}/{remote_name}"
            dst = self.local_fs.path(item["name"])

        def after_confirm(result):
            if not result:
                return
            asyncio.create_task(self._copy_worker())

        self.app.push_screen(
                ConfirmDialog(f"Transfer '{src}' to '{dst}'?"),
                callback=after_confirm
        )

    def action_switch(self):
        if self.active == "local":

            self.active = "remote"
            self.set_focus(self.remote_table)

        elif self.active == "remote":

            self.active = "local"
            self.set_focus(self.local_table)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        table = self.get_active()
        item = table.selected()

        if not item.get("is_dir"):
            return

        if table == self.local_table:
            self.local_fs.cd(item["name"])
            self.local_path_line.path = self.local_fs.cwd
            self.refresh_local()
        else:
            self.remote_fs.cd(item["name"])
            self.remote_path_line.path = f"{self.remote_fs.repo}/{self.remote_fs.path_str}"
            self.refresh_remote()

    @on(FilterBar.Changed)
    def on_filter_bar_changed(self, event: FilterBar.Changed):
        if event.sender == self.query_one("#local-filter", FilterBar):
            self.local_table.apply_filter(event.value)

        elif event.sender == self.query_one("#remote-filter", FilterBar):
            self.remote_table.apply_filter(event.value)

    def action_refresh(self):
        self.refresh_local()
        self.refresh_remote()

    def action_quit(self):
        sys.exit()
