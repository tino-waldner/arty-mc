import asyncio
from core.api_client import ArtifactoryAPI
from artifactory import ArtifactoryPath

class ArtifactoryFS:

    def __init__(self, config):
        self.api = ArtifactoryAPI(config)
        self.repo = config["default_repo"]
        self.path_str = ""
        self.server = config["server"]
        self.auth = self.api.session.session.auth

    def list(self):
        return self.api.list_folder(
            self.repo,
            self.path_str
        )

    def cd(self, name):
        if self.path_str:
            self.path_str += "/" + name
        else:
            self.path_str = name

    def up(self):
        parts = self.path_str.split("/")
        self.path_str = "/".join(parts[:-1])

    async def delete(self, name: str, progress_callback: None):
        await asyncio.to_thread(self._delete, name, progress_callback)

    def _delete(self, name, progress_callback):
        remote_full_path = self.path(name)
        url = f"{self.server}/{self.repo}/{remote_full_path}"
        remote = ArtifactoryPath(url, auth=self.auth)

        if remote.is_file():
            total = 1
            if progress_callback:
                progress_callback("start", total)
            remote.unlink()
            if progress_callback:
                progress_callback("advance", 1)
                progress_callback("finish", None)
            return

        if not remote.is_dir():
            return

        total = len(list(remote.glob("*")))
        if progress_callback:
            progress_callback("start", total)

        for child in remote.glob("*"):
            self._delete_path_recursive(child, progress_callback)
        remote.rmdir()
        if progress_callback:
            progress_callback("advance", 1)
            progress_callback("finish", None)

    def _delete_path_recursive(self, path: ArtifactoryPath, progress_callback):
        if path.is_file():
            path.unlink()
            if progress_callback:
                progress_callback("advance", 1)
        elif path.is_dir():
            for child in path.glob("*"):
                self._delete_path_recursive(child, progress_callback)
                if progress_callback:
                    progress_callback("advance", 1)
            path.rmdir()
            if progress_callback:
                progress_callback("advance", 1)

    def path(self, name):
        if self.path_str:
            return f"{self.path_str}/{name}"
        return name
