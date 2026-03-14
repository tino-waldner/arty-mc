import asyncio
import os
from datetime import datetime
from typing import Optional

MAX_CONCURRENCY = 4


class LocalFS:
    def __init__(self):
        self.cwd = os.getcwd()

    def list(self):
        items = []
        for e in os.scandir(self.cwd):
            stat = None
            is_dir = False
            size = 0
            modified = None
            try:
                stat = e.stat(follow_symlinks=False) if e.is_symlink() else e.stat()
                is_dir = e.is_dir(follow_symlinks=False)
                size = stat.st_size if stat else 0
                modified = (
                    datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    if stat
                    else None
                )
            except Exception:
                pass
            items.append(
                {
                    "name": e.name,
                    "path": e.path,
                    "is_dir": is_dir,
                    "size": size,
                    "modified": modified,
                }
            )
        items.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
        return items

    def cd(self, name):
        self.cwd = os.path.join(self.cwd, name)

    def up(self):
        self.cwd = os.path.dirname(self.cwd)

    def path(self, name):
        return os.path.join(self.cwd, name)

    async def delete(
        self,
        name: str,
        progress_callback=None,
        cancel_event: Optional[asyncio.Event] = None,
    ):
        cancel_event = cancel_event or asyncio.Event()
        path = os.path.normpath(self.path(name))
        if not os.path.exists(path):
            return

        items_to_delete = []
        for dirpath, dirnames, filenames in os.walk(path, topdown=False):
            for f in filenames:
                items_to_delete.append(os.path.join(dirpath, f))
            for d in dirnames:
                items_to_delete.append(os.path.join(dirpath, d))
        items_to_delete.append(path)

        total = len(items_to_delete)
        if progress_callback:
            progress_callback("start", total)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def delete_item(p):
            if cancel_event.is_set():
                return
            async with semaphore:
                await asyncio.to_thread(self._delete_item, p, progress_callback)

        await asyncio.gather(*(delete_item(p) for p in items_to_delete))

        if progress_callback:
            progress_callback("finish", None)

    def _delete_item(self, path, progress_callback=None):
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                os.rmdir(path)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

        if progress_callback:
            progress_callback("advance", 1)
