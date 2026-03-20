from datetime import datetime

import requests  # type: ignore
from artifactory import ArtifactoryException, ArtifactoryPath  # type: ignore

from arty_mc.auth import AuthSession


class ArtifactoryAPI:
    def __init__(self, config):
        self.session = AuthSession(config["server"], config["user"], config["token"])
        self.base_url = config["server"].rstrip("/")
        self.apikey = config["token"]
        self._license: str | None = None

    def get_license(self) -> str:
        """Return the Artifactory license type e.g. 'OSS', 'Pro', 'Enterprise'.

        Cached after the first call. Returns 'unknown' on any error.
        """
        if self._license is not None:
            return self._license
        try:
            data = self.session.get("/api/system/version")
            self._license = data.get("license", "unknown")
        except Exception:
            self._license = "unknown"
        return self._license

    def has_aql(self) -> bool:
        """Return True if this Artifactory instance supports AQL search."""
        return self.get_license().upper() not in ("OSS", "UNKNOWN")

    def list_folder(self, repo, path=""):
        repo_path = f"{repo}/{path.lstrip('/').rstrip('/')}"
        full_url = f"{self.base_url}/{repo_path}"

        items = []

        try:
            folder = ArtifactoryPath(full_url, apikey=self.apikey)

            for child in folder.iterdir():
                st = child.stat()
                is_dir = st.is_dir
                size = "-" if is_dir else getattr(st, "size", 0)
                modified_dt = getattr(st, "last_modified", None)
                if modified_dt is None:
                    try:
                        props = child.properties
                        modified_dt = props.get("lastModified")
                    except Exception:
                        modified_dt = None

                if isinstance(modified_dt, datetime):
                    modified = modified_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    modified = None

                items.append(
                    {
                        "name": child.name,
                        "is_dir": is_dir,
                        "size": size,
                        "modified": modified,
                    }
                )

            return items

        except (ArtifactoryException, requests.exceptions.RequestException) as e:
            raise RuntimeError(f"Cannot reach Artifactory server API: {e}")
