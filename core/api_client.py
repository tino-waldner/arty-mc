from auth import AuthSession


class ArtifactoryAPI:

    def __init__(self, config):
        self.session = AuthSession(
            config["server"],
            config["user"],
            config["token"]
        )

    def list_repositories(self):
        data = self.session.get("/api/repositories")
        return [r["key"] for r in data]

    def list_folder(self, repo, path=""):
        url = f"/api/storage/{repo}/{path}"
        data = self.session.get(url)
        items = []

        for c in data.get("children", []):
            items.append(
                {
                    "name": c["uri"].lstrip("/"),
                    "is_dir": c["folder"],
                }
            )

        return items

    def properties(self, repo, path):
        return self.session.get(f"/api/storage/{repo}/{path}")
