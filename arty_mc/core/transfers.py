import asyncio
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from artifactory import ArtifactoryPath  # type: ignore
from requests import Session  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3.util.retry import Retry

from arty_mc.core.fs_utils import is_accessible

CHUNK_SIZE = 4 * 1024 * 1024
CONCURRENCY_LIMIT = 4

_aql_available: Optional[bool] = None


class TransferEntry:
    def __init__(self, local: Path, remote: str, is_dir: bool, size: int = 0):
        self.local = local
        self.remote = remote
        self.is_dir = is_dir
        self.size = size


class ProgressFile:
    def __init__(self, path: Path, callback=None, cancel_event: Optional[asyncio.Event] = None):
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

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
    session.mount("http://", adapter)  # noqa: S507 # nosec
    session.mount("https://", adapter)

    return session


def upload_file(entry, session, auth=None, progress_callback=None, cancel_event=None):
    cancel_event = cancel_event or asyncio.Event()
    if cancel_event.is_set():
        return
    with ProgressFile(entry.local, progress_callback, cancel_event) as pf:
        r = session.put(entry.remote, data=pf, auth=auth, headers={"Expect": "100-continue"})
        r.raise_for_status()


async def upload_file_limited(
    entry, session, semaphore, auth=None, progress_callback=None, cancel_event=None
):
    async with semaphore:
        await asyncio.to_thread(upload_file, entry, session, auth, progress_callback, cancel_event)


async def expand_upload_entries(entries: List[TransferEntry], auth=None) -> List[TransferEntry]:
    expanded = []

    for entry in entries:
        if not entry.is_dir:
            if not is_accessible(entry.local):
                continue
            expanded.append(entry)
            continue

        remote_root = ArtifactoryPath(entry.remote, auth=auth)

        for local_path in entry.local.rglob("*"):
            if not is_accessible(local_path):
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
    entries: List[TransferEntry],
    auth=None,
    progress_callback=None,
    cancel_event=None,
):
    cancel_event = cancel_event or asyncio.Event()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    session = create_session()
    entries = await expand_upload_entries(entries, auth)

    total_bytes = sum(entry.local.stat().st_size for entry in entries if not entry.is_dir)
    if progress_callback:
        progress_callback("start", total_bytes)

    tasks = [
        upload_file_limited(entry, session, semaphore, auth, progress_callback, cancel_event)
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
    entry.local.parent.mkdir(parents=True, exist_ok=True)

    with session.get(entry.remote, stream=True, auth=auth) as r:
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
    entry, session, semaphore, auth=None, progress_callback=None, cancel_event=None
):
    async with semaphore:
        await asyncio.to_thread(
            download_file, entry, session, auth, progress_callback, cancel_event
        )


def _aql_expand_entry(
    entry: TransferEntry,
    base_url: str,
    session: Session,
    auth,
    warn_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[List[TransferEntry], int]:
    global _aql_available

    if _aql_available is False:
        return _rglob_expand_entry(entry, auth)

    artifactory_base = base_url.rstrip("/") + "/artifactory"
    rel = entry.remote[len(artifactory_base) :].lstrip("/")
    parts = rel.split("/", 1)
    repo = parts[0]
    folder_path = parts[1] if len(parts) > 1 else "."

    if folder_path == ".":
        path_clause = '"path": {"$match": "*"}'
    else:
        path_clause = (
            f'"$or": [{{"path": "{folder_path}"}}, {{"path": {{"$match": "{folder_path}/*"}}}}]'
        )

    aql = (
        f"items.find({{"
        f'"repo": "{repo}", '
        f'"type": "file", '
        f"{path_clause}"
        f'}}).include("repo", "path", "name", "size")'
    )

    aql_url = f"{artifactory_base}/api/search/aql"

    try:
        r = session.post(
            aql_url,
            data=aql,
            auth=auth,
            headers={"Content-Type": "text/plain"},
            timeout=30,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        _aql_available = True
    except Exception as e:
        _aql_available = False
        if warn_callback:
            warn_callback(
                f"AQL search not available ({e}). "
                f"This is expected on Artifactory OSS. "
                f"Downloads will use a slower directory walk."
            )
        return _rglob_expand_entry(entry, auth)

    expanded = []
    total_bytes = 0

    for item in results:
        item_path = item["path"]
        item_name = item["name"]
        size = item.get("size", 0)

        remote_file_url = f"{artifactory_base}/{repo}/{item_path}/{item_name}"

        if folder_path == ".":
            rel_path = Path(item_path) / item_name if item_path != "." else Path(item_name)
        else:
            full_item_path = f"{item_path}/{item_name}"
            try:
                rel_path = Path(full_item_path).relative_to(folder_path)
            except ValueError:
                rel_path = Path(item_name)

        local_path = entry.local / rel_path
        total_bytes += size

        expanded.append(
            TransferEntry(
                local=local_path,
                remote=remote_file_url,
                is_dir=False,
                size=size,
            )
        )

    return expanded, total_bytes


def _rglob_expand_entry(entry: TransferEntry, auth) -> Tuple[List[TransferEntry], int]:
    root = ArtifactoryPath(entry.remote, auth=auth)
    entry.local.mkdir(parents=True, exist_ok=True)

    expanded = []
    total_bytes = 0

    for child in root.rglob("*"):
        rel = child.relative_to(root)
        local_path = entry.local / str(rel)

        if child.is_dir():
            local_path.mkdir(parents=True, exist_ok=True)
        else:
            try:
                size = child.stat().st_size
            except Exception:
                size = 0
            total_bytes += size
            expanded.append(
                TransferEntry(
                    local=local_path,
                    remote=str(child),
                    is_dir=False,
                    size=size,
                )
            )

    return expanded, total_bytes


async def expand_entries(
    entries: List[TransferEntry],
    base_url: str,
    session: Session,
    auth,
    warn_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[List[TransferEntry], int]:
    expanded = []
    total_bytes = 0

    for entry in entries:
        if not entry.is_dir:
            try:
                r = session.head(entry.remote, auth=auth, timeout=10)
                size = int(r.headers.get("Content-Length", 0))
            except Exception:
                size = 0
            total_bytes += size
            expanded.append(
                TransferEntry(local=entry.local, remote=entry.remote, is_dir=False, size=size)
            )
        else:
            sub_entries, sub_bytes = await asyncio.to_thread(
                _aql_expand_entry, entry, base_url, session, auth, warn_callback
            )
            expanded.extend(sub_entries)
            total_bytes += sub_bytes

    return expanded, total_bytes


async def download(
    entries: List[TransferEntry],
    base_url: str,
    auth=None,
    progress_callback=None,
    cancel_event=None,
    warn_callback: Optional[Callable[[str], None]] = None,
    use_aql: bool = True,
):
    global _aql_available
    cancel_event = cancel_event or asyncio.Event()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    session = create_session()

    if not use_aql:
        _aql_available = False

    entries, total_bytes = await expand_entries(entries, base_url, session, auth, warn_callback)

    if progress_callback:
        progress_callback("start", total_bytes)

    tasks = [
        download_file_limited(entry, session, semaphore, auth, progress_callback, cancel_event)
        for entry in entries
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass

    if progress_callback:
        progress_callback("finish", None)
