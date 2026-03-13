import asyncio
from concurrent.futures import ThreadPoolExecutor
from core.api_client import ArtifactoryAPI
from artifactory import ArtifactoryPath
from pathlib import Path

MAX_CONCURRENCY = 6

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

    async def delete(self, name: str, progress_callback=None):
        await asyncio.to_thread(self._delete, name, progress_callback)

    def _delete(self, name, progress_callback=None):
        remote_full_path = self.path(name)
        url = f"{self.server}/{self.repo}/{remote_full_path}"
        remote = ArtifactoryPath(url, auth=self.auth)
        items_to_delete = []

        if remote.is_file():
            items_to_delete.append(remote)
        elif remote.is_dir():
            items_to_delete.extend(sorted(remote.glob("**/*"), key=lambda x: x.is_dir()))
            items_to_delete.append(remote)

        total = len(items_to_delete)

        if progress_callback:
            progress_callback("start", total)

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
            futures = []
            for item in items_to_delete:
                futures.append(executor.submit(self._delete_item, item, progress_callback))

            for future in futures:
                future.result()

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
        except Exception:
            pass
        if progress_callback:
            progress_callback("advance", 1)

    def path(self, name):
        if self.path_str:
            return f"{self.path_str}/{name}"
        return name
