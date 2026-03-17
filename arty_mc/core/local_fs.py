import asyncio
import os
import shutil
from datetime import datetime

MAX_CONCURRENCY = 4


class FileEntry:
    def __init__(self, path: str, is_dir: bool):
        self.path = path
        self.is_dir = is_dir
        self.name = os.path.basename(os.path.normpath(path))  # introduce for tests


class LocalFS:
    def __init__(self):
        self.cwd = os.getcwd()

    def list(self):
        items = []
        for e in os.scandir(self.cwd):
            is_dead_symlink = False
            is_empty_dir = False
            is_dir = False
            size = 0
            modified = None

            try:
                if e.is_symlink():
                    if not os.path.exists(e.path):
                        is_dead_symlink = True
                    else:
                        is_dir = e.is_dir(follow_symlinks=True)
                        stat = e.stat()
                        size = stat.st_size
                        modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                else:
                    is_dir = e.is_dir()
                    stat = e.stat()
                    size = stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            except Exception:
                pass

            if is_dir:
                try:
                    is_empty_dir = len(os.listdir(e.path)) == 0
                except Exception:
                    is_empty_dir = False

            items.append(
                {
                    "name": e.name,
                    "path": e.path,
                    "is_dir": is_dir,
                    "size": size,
                    "modified": modified,
                    "is_dead_symlink": is_dead_symlink,
                    "is_empty_dir": is_empty_dir,
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

    async def delete(self, name: str, progress_callback=None, cancel_event=None):
        cancel_event = cancel_event or asyncio.Event()
        path = os.path.normpath(self.path(name))

        if not os.path.exists(path):
            return

        if progress_callback:
            progress_callback("start", 1)

        await asyncio.to_thread(self._delete_item, path, progress_callback)

        if progress_callback:
            progress_callback("finish", None)

    def _delete_item(self, path, progress_callback=None):
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

        if progress_callback:
            progress_callback("advance", 1)
