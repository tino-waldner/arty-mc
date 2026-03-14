import asyncio
from typing import Optional

from artifactory import ArtifactoryPath  # type: ignore

from core.api_client import ArtifactoryAPI

MAX_CONCURRENCY = 4


class ArtifactoryFS:
    def __init__(self, config):
        self.api = ArtifactoryAPI(config)
        self.repo = config["default_repo"]
        self.path_str = ""
        self.server = config["server"]
        self.auth = self.api.session.session.auth

    def list(self):
        items = self.api.list_folder(self.repo, self.path_str)
        items.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
        return items

    def cd(self, name):
        if self.path_str:
            self.path_str += "/" + name
        else:
            self.path_str = name

    def up(self):
        parts = self.path_str.split("/")
        self.path_str = "/".join(parts[:-1])

    def path(self, name):
        if self.path_str:
            return f"{self.path_str}/{name}"
        return name

    async def delete(
        self,
        name: str,
        progress_callback=None,
        cancel_event: Optional[asyncio.Event] = None,
    ):
        if cancel_event is None:
            cancel_event = asyncio.Event()

        await self._delete(name, progress_callback, cancel_event)

    async def _delete(
        self,
        name: str,
        progress_callback=None,
        cancel_event: Optional[asyncio.Event] = None,
    ):
        if cancel_event is None:
            cancel_event = asyncio.Event()

        remote_full_path = self.path(name)
        remote = ArtifactoryPath(
            f"{self.server}/{self.repo}/{remote_full_path}", auth=self.auth
        )

        items_to_delete = []
        if remote.is_file():
            items_to_delete.append(remote)
        elif remote.is_dir():
            for item in sorted(remote.glob("**/*"), key=lambda x: x.is_dir()):
                items_to_delete.append(item)
            items_to_delete.append(remote)

        total = len(items_to_delete)
        if progress_callback:
            progress_callback("start", total)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def delete_item(item):
            if cancel_event and cancel_event.is_set():
                return
            async with semaphore:
                await asyncio.to_thread(self._delete_item, item, progress_callback)

        tasks = [delete_item(item) for item in items_to_delete]
        await asyncio.gather(*tasks)

        if progress_callback:
            progress_callback("finish", None)

    def _delete_item(self, item, progress_callback=None):
        """Blocking delete of a single file or folder."""
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                try:
                    item.rmdir()
                except Exception:
                    pass
        except Exception:
            pass
        if progress_callback:
            progress_callback("advance", 1)
