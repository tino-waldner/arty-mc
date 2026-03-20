import asyncio
from typing import Optional

from artifactory import ArtifactoryPath  # type: ignore

from arty_mc.core.api_client import ArtifactoryAPI

MAX_CONCURRENCY = 4


class FileEntry:
    def __init__(self, repo, name, is_dir, size=None, modified=None):
        self.repo = repo
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.modified = modified

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class ArtifactoryFS:
    def __init__(self, config):
        self.api = ArtifactoryAPI(config)
        self.repo = config["default_repo"]
        self.server = config["server"]
        self.auth = self.api.session.session.auth
        self._cwd = ""

    def list(self):
        items = self.api.list_folder(self.repo, self._cwd)
        items.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
        return [
            FileEntry(
                self.repo,
                f["name"],
                f["is_dir"],
                size=f.get("size"),
                modified=f.get("modified"),
            )
            for f in items
        ]

    def cd(self, name: str):
        if self._cwd:
            self._cwd += "/" + name
        else:
            self._cwd = name

    def up(self):
        if not self._cwd:
            return
        parts = self._cwd.split("/")
        self._cwd = "/".join(parts[:-1])

    @property
    def path_str(self):
        return self._cwd

    def path(self, name: str):
        return f"{self._cwd}/{name}" if self._cwd else name

    async def delete(
        self,
        entry,
        progress_callback=None,
        cancel_event: Optional[asyncio.Event] = None,
    ):

        cancel_event = cancel_event or asyncio.Event()
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        try:
            remote_root = ArtifactoryPath(
                f"{self.server}/{entry.repo}/{self.path(entry.name)}",
                auth=self.auth,
            )
        except Exception as e:
            raise RuntimeError(f"Cannot reach Artifactory: {e}") from e

        delete_queue = [remote_root]

        if progress_callback:
            progress_callback("start", None)

        async def delete_worker(item):
            if cancel_event.is_set():
                return  # pragma: no cover
            async with semaphore:
                await asyncio.to_thread(self._delete_item, item, progress_callback)

        try:
            while delete_queue:
                current = delete_queue.pop(0)
                if cancel_event.is_set():
                    break

                try:
                    is_file = current.is_file()
                    is_dir = current.is_dir()
                except Exception as e:
                    raise RuntimeError(
                        f"Connection lost during delete: {e}"
                    ) from e

                if is_file:
                    if progress_callback:
                        progress_callback("add_total", 1)
                    await delete_worker(current)
                elif is_dir:
                    try:
                        children = list(current.iterdir())
                    except Exception as e:
                        raise RuntimeError(
                            f"Connection lost while listing directory: {e}"
                        ) from e

                    for child in children:
                        delete_queue.append(child)
                        if progress_callback:
                            progress_callback("add_total", 1)

                    await delete_worker(current)
        finally:
            if progress_callback:
                progress_callback("finish", None)

    def _delete_item(self, item, progress_callback=None):
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                try:
                    item.rmdir()
                except Exception:
                    pass
        except Exception as e:
            raise RuntimeError(f"Failed to delete {item}: {e}") from e
        finally:
            if progress_callback:
                progress_callback("advance", 1)
