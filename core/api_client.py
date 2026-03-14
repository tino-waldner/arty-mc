from datetime import datetime

import requests  # type: ignore
from artifactory import ArtifactoryException, ArtifactoryPath  # type: ignore

from auth import AuthSession


class ArtifactoryAPI:
    def __init__(self, config):
        self.session = AuthSession(config["server"], config["user"], config["token"])
        self.base_url = config["server"].rstrip("/")
        self.apikey = config["token"].rstrip("/")

    def list_repositories(self):
        data = self.session.get("/api/repositories")
        return [r["key"] for r in data]

    def list_folder(self, repo, path=""):
        repo_path = f"{repo}/{path.lstrip('/').rstrip('/')}"
        full_url = f"{self.base_url}/{repo_path}"
        items = []

        try:
            folder = ArtifactoryPath(full_url, apikey=self.apikey)

            for child in folder.iterdir():
                st = child.stat()
                size = st.st_size if st and not st.is_dir else "-"

                if isinstance(st.mtime, (int, float)):
                    modified = datetime.fromtimestamp(st.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                elif isinstance(st.mtime, datetime):
                    modified = st.mtime.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    modified = None

                items.append(
                    {
                        "name": child.name,
                        "is_dir": st.is_dir,
                        "size": size,
                        "modified": modified,
                    }
                )
            return items
        except (ArtifactoryException, requests.exceptions.RequestException) as e:
            raise RuntimeError(f"Cannot reach Artifactory server API: {e}")

    def properties(self, repo, path):
        return self.session.get(f"/api/storage/{repo}/{path}")
