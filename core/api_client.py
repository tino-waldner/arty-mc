from auth import AuthSession
from artifactory import ArtifactoryPath
from datetime import datetime


class ArtifactoryAPI:
    def __init__(self, config):
        self.session = AuthSession(
            config["server"],
            config["user"],
            config["token"]
        )
        self.base_url = config["server"].rstrip('/')
        self.apikey = config["token"].rstrip('/')

    def list_repositories(self):
        data = self.session.get("/api/repositories")
        return [r["key"] for r in data]

    def list_folder(self, repo, path=""):
        repo_path = f"{repo}/{path.lstrip('/').rstrip('/')}"
        full_url = f"{self.base_url}/{repo_path}"

        folder = ArtifactoryPath(
            full_url,
            apikey = self.apikey
        )

        items = []

        for child in folder.iterdir():
            st = child.stat()
            size = st.size if not st.is_dir else 0

            if isinstance(st.mtime, (int, float)):
               modified = datetime.fromtimestamp(st.mtime).isoformat()
            elif isinstance(st.mtime, datetime):
               modified = st.mtime.isoformat()
            else:
               modified = None

            items.append({
                "name": child.name,
                "is_dir": st.is_dir,
                "size": size,
                "modified": modified,
            })
        return items

    def properties(self, repo, path):
        return self.session.get(f"/api/storage/{repo}/{path}")
