import asyncio
from typing import Optional

from arty_mc.core.api_client import ArtifactoryAPI


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

        if progress_callback:
            progress_callback("start", None)

        try:
            if cancel_event.is_set():
                return

            url = f"{self.server}/{entry.repo}/{self.path(entry.name)}"

            if progress_callback:
                progress_callback("add_total", 1)

            await asyncio.to_thread(self._delete_item, url, progress_callback)

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Cannot reach Artifactory: {e}") from e
        finally:
            if progress_callback:
                progress_callback("finish", None)

    def _delete_item(self, url, progress_callback=None):
        try:
            r = self.api.session.session.delete(url, timeout=300)
            r.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to delete {url}: {e}") from e
        finally:
            if progress_callback:
                progress_callback("advance", 1)
