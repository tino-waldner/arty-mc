import asyncio
import os
from pathlib import Path
from artifactory import ArtifactoryPath
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CHUNK_SIZE = 4 * 1024 * 1024
CONCURRENCY_LIMIT = 3


class ProgressFile:

    def __init__(self, path: Path, callback=None):
        self.file = open(path, "rb")
        self.callback = callback
        self.size = path.stat().st_size
        self.read_bytes = 0

    def read(self, size=-1):
        chunk = self.file.read(size)
        if chunk:
            self.read_bytes += len(chunk)
            if self.callback:
                self.callback("advance", len(chunk))
        return chunk

    def __len__(self):
        return self.size

    def close(self):
        self.file.close()

    def __getattr__(self, name):
        return getattr(self.file, name)


def create_session():

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "PUT", "HEAD"],
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=CONCURRENCY_LIMIT,
        pool_maxsize=CONCURRENCY_LIMIT,
    )

    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def upload_file(local_file: Path, remote_url: str, session: Session, auth=None, progress_callback=None):

    total = local_file.stat().st_size

    if progress_callback:
        progress_callback("start", total)

    pf = ProgressFile(local_file, progress_callback)

    try:
        r = session.put(
            remote_url,
            data=pf,
            auth=auth,
            headers={"Expect": "100-continue"},
        )
        r.raise_for_status()
    finally:
        pf.close()

    if progress_callback:
        progress_callback("finish", None)


upload_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def upload_file_limited(local_file: Path, remote_url: str, session: Session, auth=None, progress_callback=None):
    async with upload_semaphore:
        await asyncio.to_thread(upload_file, local_file, remote_url, session, auth, progress_callback)


async def upload(local_path: str, remote_path: str, remote_repo_url=None, auth=None, progress_callback=None):

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

    tasks = []

    for file in files:

        rel = file.relative_to(base)

        remote_url = "/".join(
            part.strip("/") for part in [remote_repo_url, remote_path, rel.as_posix()] if part
        )

        tasks.append(
            upload_file_limited(file, remote_url, session, auth, progress_callback)
        )

    await asyncio.gather(*tasks)

    if progress_callback:
        progress_callback("finish", None)


def download_file(remote_file: ArtifactoryPath, local_file: Path, session: Session, auth=None, progress_callback=None):

    total = remote_file.stat().st_size

    if progress_callback:
        progress_callback("start", total)

    downloaded = 0

    local_file.parent.mkdir(parents=True, exist_ok=True)

    with session.get(str(remote_file), stream=True, auth=auth) as r:

        r.raise_for_status()

        with open(local_file, "wb") as f:

            for chunk in r.iter_content(CHUNK_SIZE):

                f.write(chunk)

                downloaded += len(chunk)

                if progress_callback:
                    progress_callback("advance", len(chunk))

    if progress_callback:
        progress_callback("finish", None)


download_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def download_file_limited(remote_file: ArtifactoryPath, local_file: Path, session: Session, auth=None, progress_callback=None):
    async with download_semaphore:
        await asyncio.to_thread(download_file, remote_file, local_file, session, auth, progress_callback)


async def download(remote_path: str, local_path: str, remote_repo_url=None, auth=None, progress_callback=None):

    if remote_repo_url is None:
        raise ValueError("remote_repo_url is None")

    session = create_session()

    local_base = Path(local_path)

    remote = ArtifactoryPath(f"{remote_repo_url}/{remote_path}", auth=auth)

    files = []

    if remote.is_file():

        files.append((remote, local_base / remote.name))

    else:

        top_folder = Path(remote.name)

        local_base = local_base / top_folder

        for item in remote.glob("**/*"):

            if item.is_file():

                relative = item.relative_to(remote)

                files.append((item, local_base / relative))

    tasks = [
        download_file_limited(rf, lf, session, auth, progress_callback)
        for rf, lf in files
    ]

    await asyncio.gather(*tasks)
