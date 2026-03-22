import asyncio
import os
import shutil
import stat
from datetime import datetime

from arty_mc.core.fs_utils import is_accessible, is_copyable

MAX_CONCURRENCY = 4


class FileEntry:
    def __init__(self, path: str, is_dir: bool):
        self.path = path
        self.is_dir = is_dir
        self.name = os.path.basename(os.path.normpath(path))


class LocalFS:
    def __init__(self):
        self.cwd = os.getcwd()

    def list(self):
        items = []

        for e in os.scandir(self.cwd):
            path = e.path
            size = 0
            is_dir = False
            modified = None
            is_unreadable = False
            is_dead_symlink = False
            is_empty_dir = False
            is_symlink = os.path.islink(path)

            try:
                if is_symlink and not os.path.exists(path):
                    is_dead_symlink = True
                    is_unreadable = True
                    raise Exception("broken symlink")

                real_path = os.path.realpath(path)
                st = os.stat(real_path)
                size = st.st_size
                modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                mode = st.st_mode
                if stat.S_ISDIR(mode):
                    is_dir = True
                    if not (os.access(real_path, os.R_OK) and os.access(real_path, os.X_OK)):
                        is_unreadable = True
                    else:
                        try:
                            contents = os.listdir(real_path)
                            is_empty_dir = len(contents) == 0
                        except Exception:
                            is_unreadable = True
                elif stat.S_ISREG(mode):
                    if not os.access(real_path, os.R_OK):
                        is_unreadable = True
                else:
                    is_unreadable = True
            except Exception:
                if not is_dead_symlink:
                    is_unreadable = True
                size = 0
                modified = None
                is_empty_dir = False

            items.append(
                {
                    "name": e.name,
                    "path": path,
                    "is_dir": is_dir,
                    "size": size,
                    "modified": modified,
                    "is_dead_symlink": is_dead_symlink,
                    "is_unreadable": is_unreadable,
                    "is_empty_dir": is_empty_dir,
                }
            )

        items.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
        return items

    def cd(self, name) -> bool:
        target = os.path.join(self.cwd, name)
        if is_accessible(target):
            self.cwd = target
            return True
        return False

    def up(self) -> bool:
        parent = os.path.dirname(self.cwd)
        if parent == self.cwd:
            # Already at filesystem root
            return False
        if is_accessible(parent):
            self.cwd = parent
            return True
        return False

    def path(self, name):
        return os.path.join(self.cwd, name)

    def is_accessible_from_ui(self, path) -> bool:
        return is_copyable(path)

    def is_deletable_from_ui(self, path) -> bool:
        return is_accessible(path)

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
            if is_accessible(path):
                if os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=False)
        except Exception as e:
            raise RuntimeError(f"Failed to delete {path}: {e}") from e
        finally:
            if progress_callback:
                progress_callback("advance", 1)
