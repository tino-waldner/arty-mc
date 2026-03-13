import asyncio
import shutil
import os
from pathlib import Path
from artifactory import ArtifactoryPath

async def upload(local_path: str, remote_path: str, remote_repo_url=None, auth=None, progress_callback=None):
    await asyncio.to_thread(_upload, local_path, remote_path, remote_repo_url, auth, progress_callback)

def _upload(local_path, remote_path, remote_repo_url, auth, progress_callback):
    if remote_repo_url is None:
        raise ValueError(
                "Error: 'remote_repo_url' is None"
                )

    local_path = Path(local_path)

    if local_path.is_file():
        total_files = 1
        if progress_callback:
            progress_callback("start", total_files)
        remote = ArtifactoryPath(f"{remote_repo_url}/{remote_path}/{local_path.name}", auth=auth)
        remote.deploy_file(local_path)
        if progress_callback:
            progress_callback("advance", 1)
        progress_callback("finish", None)
        return

    else:
        base = local_path.parent
        total_files = len([os.path.join(r, f) for r, _, files in os.walk(local_path) for f in files])
        if progress_callback:
            progress_callback("start", total_files)

        for root, _, files in os.walk(local_path):
            root_path = Path(root)
            for file in files:
                full_file = root_path / file
                rel_path = full_file.relative_to(base)
                remote = ArtifactoryPath(f"{remote_repo_url}/{remote_path}/{rel_path.as_posix()}", auth=auth)
                remote.deploy_file(full_file)
                if progress_callback:
                    progress_callback("advance", 1)

        if progress_callback: 
            progress_callback("finish", None)

async def download(remote_path: str, local_path: str, remote_repo_url=None, auth=None, progress_callback=None):
    await asyncio.to_thread(_download, remote_path, local_path, remote_repo_url, auth, progress_callback)

def _download(remote_path, local_path, remote_repo_url, auth, progress_callback):
    if remote_repo_url is None:
        raise ValueError(
                "Error: 'remote_repo_url' is None"
                )

    remote = ArtifactoryPath(f"{remote_repo_url}/{remote_path}", auth=auth)
    local_path = Path(local_path)

    if remote.is_file():
        total_files = 1
        if progress_callback:
            progress_callback("start", total_files)
        with remote.open() as f_remote, open(local_path, "wb") as f_local:
            f_local.write(f_remote.read())
        if progress_callback:
            progress_callback("advance", 1)
            progress_callback("finish", None)

        return

    else:
        base_remote = remote

        total_files=len(list(remote.glob("**/*")))
        if progress_callback:
            progress_callback("start", total_files)

        for item in remote.glob("**/*"):

            if item.is_dir():
                continue
    
            rel_path = item.relative_to(base_remote)

            dst = local_path / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)

            with item.open() as f_remote, open(dst, "wb") as out:
                out.write(f_remote.read())

            if progress_callback:
                progress_callback("advance", 1)

        if progress_callback: 
            progress_callback("finish", None)
