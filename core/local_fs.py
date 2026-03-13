import os
import asyncio
import shutil
from datetime import datetime


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
                if e.is_symlink():
                    try:
                        stat = e.stat(follow_symlinks=False)
                    except OSError:
                        stat = None
                else:
                    stat = e.stat()
    
                is_dir = e.is_dir(follow_symlinks=False)
                size = stat.st_size if stat else 0
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S") if stat else None
    
            except Exception:
                pass
    
            items.append({
                "name": e.name,
                "path": e.path,
                "is_dir": is_dir,
                "size": size,
                "modified": modified
            })
    
        items.sort(key=lambda f: (not f["is_dir"], f["name"].lower()))
        return items

    def cd(self, name):
        self.cwd = os.path.join(self.cwd, name)

    def up(self):
        self.cwd = os.path.dirname(self.cwd)

    async def delete(self, name: str, progress_callback: None):
        await asyncio.to_thread(self._delete, name, progress_callback) 

    def _delete(self, name, progress_callback):
        path = os.path.join(self.cwd, name)
        path = os.path.normpath(path)

        if not os.path.exists(path):
            return

        if os.path.isfile(path):
            total = 1
            if progress_callback:
                progress_callback("start", total)
            os.remove(path)
            if progress_callback:
                progress_callback("advance", 1)
                progress_callback("finish", None)
            return

        if not os.path.isdir(path):
            return


        def count_items(root):
            total = 0
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                total += len(filenames)
                total += len(dirnames)
            total += 1 
            return total
        
        total = count_items(path)

        if progress_callback:
            progress_callback("start", total)
        
        for dirpath, dirnames, filenames in os.walk(path, topdown=False):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    os.remove(file_path)
                    if progress_callback:
                        progress_callback("advance", 1)
                except OSError as e:
                    print(f"Failed to remove file {file_path}: {e}")
        
            for dirname in dirnames:
                dir_path = os.path.join(dirpath, dirname)
                try:
                    os.rmdir(dir_path)
                    if progress_callback:
                        progress_callback("advance", 1)
                except OSError as e:
                    print(f"Failed to remove directory {dir_path}: {e}")
        
        try:
            os.rmdir(path)
            if progress_callback:
                progress_callback("advance", 1)
        except OSError as e:
            print(f"Failed to remove root directory {path}: {e}")
        
        if progress_callback:
            progress_callback("finish", None)
        
    def path(self, name):
        return os.path.join(self.cwd, name)
