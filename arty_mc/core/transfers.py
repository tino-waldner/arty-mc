import asyncio
from pathlib import Path
from typing import List, Optional

from artifactory import ArtifactoryPath  # type: ignore
from requests import Session  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3.util.retry import Retry

CHUNK_SIZE = 4 * 1024 * 1024
CONCURRENCY_LIMIT = 4


class TransferEntry:
    def __init__(self, local: Path, remote: str, is_dir: bool):
        self.local = local
        self.remote = remote
        self.is_dir = is_dir


class ProgressFile:
    def __init__(
        self, path: Path, callback=None, cancel_event: Optional[asyncio.Event] = None
    ):
        self.file = open(path, "rb")
        self.callback = callback
        self.size = path.stat().st_size
        self.read_bytes = 0
        self.cancel_event = cancel_event or asyncio.Event()

    def read(self, size=-1):
        if self.cancel_event.is_set():
            raise asyncio.CancelledError()

        chunk = self.file.read(size)

        if chunk and self.callback:
            self.read_bytes += len(chunk)
            self.callback("advance", len(chunk))

        return chunk

    def __len__(self):
        return self.size

    def close(self):
        self.file.close()

    def __getattr__(self, name):
        return getattr(self.file, name)


def create_session() -> Session:
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


upload_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
download_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


def upload_file(entry, session, auth=None, progress_callback=None, cancel_event=None):
    cancel_event = cancel_event or asyncio.Event()
    if cancel_event.is_set():
        return  # early exit if canceled
    pf = ProgressFile(entry.local, progress_callback, cancel_event)
    try:
        r = session.put(
            entry.remote, data=pf, auth=auth, headers={"Expect": "100-continue"}
        )
        r.raise_for_status()
    finally:
        pf.close()


async def upload_file_limited(
    entry, session, auth=None, progress_callback=None, cancel_event=None
):
    async with upload_semaphore:
        await asyncio.to_thread(
            upload_file, entry, session, auth, progress_callback, cancel_event
        )


async def expand_upload_entries(
    entries: List[TransferEntry], auth=None
) -> List[TransferEntry]:
    expanded = []

    for entry in entries:
        if not entry.is_dir:
            if entry.local.is_symlink() and not entry.local.exists():
                print(f"Skipping dead symlink: {entry.local}")
                continue
            expanded.append(entry)
            continue

        remote_root = ArtifactoryPath(entry.remote, auth=auth)

        for local_path in entry.local.rglob("*"):
            if local_path.is_symlink() and not local_path.exists():
                print(f"Skipping dead symlink: {local_path}")
                continue

            rel = local_path.relative_to(entry.local)
            remote_path = str(remote_root / rel)

            if local_path.is_dir():
                continue
            else:
                expanded.append(
                    TransferEntry(
                        local=local_path,
                        remote=remote_path,
                        is_dir=False,
                    )
                )

    return expanded


async def upload(
    entries: List[TransferEntry], auth=None, progress_callback=None, cancel_event=None
):
    cancel_event = cancel_event or asyncio.Event()
    session = create_session()
    entries = await expand_upload_entries(entries, auth)

    total_bytes = sum(
        entry.local.stat().st_size for entry in entries if not entry.is_dir
    )
    if progress_callback:
        progress_callback("start", total_bytes)

    tasks = [
        upload_file_limited(entry, session, auth, progress_callback, cancel_event)
        for entry in entries
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass

    if progress_callback:
        progress_callback("finish", None)


def download_file(
    entry: TransferEntry,
    session: Session,
    auth=None,
    progress_callback=None,
    cancel_event=None,
):
    cancel_event = cancel_event or asyncio.Event()
    remote_file = ArtifactoryPath(entry.remote, auth=auth)
    entry.local.parent.mkdir(parents=True, exist_ok=True)

    with session.get(str(remote_file), stream=True, auth=auth) as r:
        r.raise_for_status()

        with open(entry.local, "wb") as f:
            for chunk in r.iter_content(CHUNK_SIZE):
                if cancel_event.is_set():
                    raise asyncio.CancelledError()

                if chunk:
                    f.write(chunk)

                    if progress_callback:
                        progress_callback("advance", len(chunk))


async def download_file_limited(
    entry, session, auth=None, progress_callback=None, cancel_event=None
):
    async with download_semaphore:
        await asyncio.to_thread(
            download_file, entry, session, auth, progress_callback, cancel_event
        )


async def expand_entries(entries: List[TransferEntry], auth) -> List[TransferEntry]:
    expanded = []

    for entry in entries:
        if not entry.is_dir:
            expanded.append(entry)
            continue

        root = ArtifactoryPath(entry.remote, auth=auth)
        entry.local.mkdir(parents=True, exist_ok=True)

        for child in root.rglob("*"):
            rel = child.relative_to(root)

            local_path = entry.local / str(rel)

            if child.is_dir():
                local_path.mkdir(parents=True, exist_ok=True)
            else:
                expanded.append(
                    TransferEntry(
                        local=local_path,
                        remote=str(child),
                        is_dir=False,
                    )
                )

    return expanded


async def download(
    entries: List[TransferEntry], auth=None, progress_callback=None, cancel_event=None
):
    cancel_event = cancel_event or asyncio.Event()
    session = create_session()
    entries = await expand_entries(entries, auth)
    total_bytes = 0

    for entry in entries:
        try:
            remote_file = ArtifactoryPath(entry.remote, auth=auth)
            total_bytes += remote_file.stat().st_size
        except Exception:
            pass

    if progress_callback:
        progress_callback("start", total_bytes)

    tasks = [
        download_file_limited(entry, session, auth, progress_callback, cancel_event)
        for entry in entries
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass

    if progress_callback:
        progress_callback("finish", None)
