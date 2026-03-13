import asyncio
import os
from pathlib import Path
from artifactory import ArtifactoryPath
import requests
from pathlib import Path
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session():

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["PUT", "GET", "HEAD"],
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=6,
        pool_maxsize=6,
    )

    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

CHUNK_SIZE = 1024 * 1024

def upload_file(local_file, remote_url, session, auth, progress_callback):

    local_file = Path(local_file)
    total = local_file.stat().st_size

    if progress_callback:
        progress_callback("start", total)

    uploaded = 0

    def gen():
        nonlocal uploaded
        with open(local_file, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                uploaded += len(chunk)

                if progress_callback:
                    progress_callback("advance", len(chunk))

                yield chunk

    r = session.put(remote_url, data=gen(), auth=auth)

    r.raise_for_status()

    if progress_callback:
        progress_callback("finish", None)


async def upload(local_path: str, remote_path: str, remote_repo_url=None, auth=None, progress_callback=None):
    await asyncio.to_thread(_upload, local_path, remote_path, remote_repo_url, auth, progress_callback)

def _upload(local_path, remote_path, remote_repo_url, auth, progress_callback):
    local_path = Path(local_path)

    files = []
    if local_path.is_file():
        files = [local_path]
        base = local_path.parent
    else:
        base = local_path.parent 
        for root, _, fs in os.walk(local_path):
            for f in fs:
                if f.startswith("."):
                    continue
                files.append(Path(root) / f)

    total_bytes = sum(f.stat().st_size for f in files)
    if progress_callback:
        progress_callback("start", total_bytes)

    session = create_session()
    for file in files:
        rel = file.relative_to(base)

        remote_url = "/".join(
            part.strip("/") for part in [remote_repo_url, remote_path, rel.as_posix()] if part
        )

        upload_file(file, remote_url, session, auth, progress_callback)

    if progress_callback:
        progress_callback("finish", None)

async def download(remote_path: str, local_path: str, remote_repo_url=None, auth=None, progress_callback=None):
    await asyncio.to_thread(_download, remote_path, local_path, remote_repo_url, auth, progress_callback)

def _download(remote_path, local_path, remote_repo_url, auth, progress_callback):
    if remote_repo_url is None:
        raise ValueError("remote_repo_url is None")

    remote = ArtifactoryPath(f"{remote_repo_url}/{remote_path}", auth=auth)
    local_path = Path(local_path)

    files = []

    if remote.is_file():
        files.append(remote)
        base = remote.parent
        top_folder = None
    else:
        base = remote
        top_folder = Path(remote.name) 
        for item in remote.glob("**/*"):
            if item.is_file():
                files.append(item)

    if top_folder:
        local_path = local_path / top_folder

    total_bytes = sum(f.stat().st_size for f in files)
    if progress_callback:
        progress_callback("start", total_bytes)

    for file in files:
        rel = file.relative_to(base)
        dst = local_path / rel

        dst.parent.mkdir(parents=True, exist_ok=True)

        with file.open() as src, open(dst, "wb") as out:
            while chunk := src.read(CHUNK_SIZE):
                out.write(chunk)
                if progress_callback:
                    progress_callback("advance", len(chunk))

    if progress_callback:
        progress_callback("finish", None)
