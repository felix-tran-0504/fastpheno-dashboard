#!/usr/bin/env python3
"""Sync selected III_db_final folders from ffgg-fastpheno2 via SSH/SFTP."""

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

from fastpheno_env import (
    DEFAULT_SYNC_FOLDERS,
    get_iii_db_root,
    get_remote_config,
    get_sync_folders,
    load_env,
    require_remote_config,
)

load_env()


def _connect_sftp(cfg: dict):
    try:
        import paramiko
    except ImportError as exc:
        raise SystemExit(
            "paramiko is required for remote sync. Run: pip install paramiko"
        ) from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": str(cfg["host"]),
        "port": int(cfg["port"]),
        "username": str(cfg["user"]),
        "timeout": 60,
        "allow_agent": True,
        "look_for_keys": True,
    }
    if cfg.get("ssh_key"):
        connect_kwargs["key_filename"] = str(Path(str(cfg["ssh_key"])).expanduser())
    if cfg.get("password"):
        connect_kwargs["password"] = str(cfg["password"])

    client.connect(**connect_kwargs)
    return client, client.open_sftp()


def _resolve_remote_root(sftp, remote_path: str) -> str:
    remote_path = remote_path.strip() or "III_db_final"
    if remote_path.startswith("/"):
        return remote_path
    home = sftp.normalize(".")
    return sftp.normalize(f"{home}/{remote_path}")


def list_remote(path: str | None = None, *, depth: int = 2) -> None:
    cfg = require_remote_config()
    client, sftp = _connect_sftp(cfg)
    try:
        root = _resolve_remote_root(sftp, path or str(cfg["remote_path"]))
        print(f"Connected to {cfg['user']}@{cfg['host']}")
        print(f"Remote root: {root}")
        print(f"Configured sync folders: {', '.join(get_sync_folders())}\n")
        _walk_remote_listing(sftp, root, prefix="", depth=depth, max_depth=depth)
    finally:
        sftp.close()
        client.close()


def _walk_remote_listing(sftp, remote_dir: str, *, prefix: str, depth: int, max_depth: int) -> None:
    if depth > max_depth:
        return
    try:
        entries = sorted(sftp.listdir_attr(remote_dir), key=lambda e: e.filename)
    except OSError as exc:
        print(f"{prefix}[error listing {remote_dir}: {exc}]")
        return
    for entry in entries:
        name = entry.filename
        if name in (".", ".."):
            continue
        full = sftp.normalize(f"{remote_dir}/{name}")
        kind = "dir" if stat.S_ISDIR(entry.st_mode) else "file"
        size = entry.st_size if kind == "file" else ""
        if kind == "dir":
            tag = " [sync]" if name in get_sync_folders() else " [skip]"
            print(f"{prefix}{name}/{tag}")
        else:
            print(f"{prefix}{name}  ({size} bytes)")
        if kind == "dir" and depth < max_depth:
            _walk_remote_listing(
                sftp, full, prefix=prefix + "  ", depth=depth + 1, max_depth=max_depth
            )


def _should_skip_download(sftp, remote_path: str, local_path: Path) -> bool:
    if not local_path.is_file():
        return False
    try:
        attr = sftp.stat(remote_path)
    except OSError:
        return False
    if attr.st_size != local_path.stat().st_size:
        return False
    remote_mtime = int(attr.st_mtime)
    local_mtime = int(local_path.stat().st_mtime)
    return local_mtime >= remote_mtime


def _download_tree(sftp, remote_dir: str, local_dir: Path, *, dry_run: bool) -> tuple[int, int]:
    downloaded = 0
    skipped = 0
    local_dir.mkdir(parents=True, exist_ok=True)
    for entry in sftp.listdir_attr(remote_dir):
        name = entry.filename
        if name in (".", ".."):
            continue
        remote_path = sftp.normalize(f"{remote_dir}/{name}")
        local_path = local_dir / name
        if stat.S_ISDIR(entry.st_mode):
            sub_dl, sub_skip = _download_tree(
                sftp, remote_path, local_path, dry_run=dry_run
            )
            downloaded += sub_dl
            skipped += sub_skip
            continue
        if _should_skip_download(sftp, remote_path, local_path):
            skipped += 1
            continue
        if dry_run:
            print(f"  would download {remote_path} -> {local_path}")
            downloaded += 1
            continue
        local_path.parent.mkdir(parents=True, exist_ok=True)
        sftp.get(remote_path, str(local_path))
        downloaded += 1
    return downloaded, skipped


def sync(
    *,
    dry_run: bool = False,
    remote_path: str | None = None,
    folders: list[str] | None = None,
    sync_all: bool = False,
) -> Path:
    cfg = require_remote_config()
    local_root = get_iii_db_root()
    folder_list = folders if folders is not None else get_sync_folders()
    client, sftp = _connect_sftp(cfg)
    try:
        remote_root = _resolve_remote_root(
            sftp, remote_path or str(cfg["remote_path"])
        )
        try:
            sftp.stat(remote_root)
        except OSError as exc:
            raise SystemExit(
                f"Remote path not found: {remote_root}\n"
                f"Run: python3 scripts/sync_iii_db_final.py --list-remote\n"
                f"Then set FASTPHENO_REMOTE_III_DB_PATH in backend/.env"
            ) from exc

        print(f"Sync {cfg['user']}@{cfg['host']}:{remote_root}")
        print(f"  -> {local_root}")
        if sync_all:
            print("Mode: full tree")
            targets = [("", remote_root, local_root)]
        else:
            print(f"Mode: selective ({len(folder_list)} folder(s))")
            print(f"  {', '.join(folder_list)}")
            targets = [
                (name, sftp.normalize(f"{remote_root}/{name}"), local_root / name)
                for name in folder_list
            ]
        if dry_run:
            print("(dry run)")

        total_downloaded = 0
        total_skipped = 0
        for name, remote_sub, local_sub in targets:
            label = name or "(root)"
            try:
                sftp.stat(remote_sub)
            except OSError:
                print(f"Warning: remote folder not found, skipping: {label}")
                continue
            print(f"\n[{label}]")
            downloaded, skipped = _download_tree(
                sftp, remote_sub, local_sub, dry_run=dry_run
            )
            total_downloaded += downloaded
            total_skipped += skipped
            print(f"  {downloaded} updated, {skipped} unchanged")

        print(
            f"\nDone: {total_downloaded} file(s) updated, "
            f"{total_skipped} unchanged skipped"
        )
        return local_root
    finally:
        sftp.close()
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync selected FastPheno folders from ffgg-fastpheno2 via SSH/SFTP"
    )
    parser.add_argument(
        "--list-remote",
        action="store_true",
        help="List remote root; folders marked for sync are noted",
    )
    parser.add_argument(
        "--remote-path",
        help="Override FASTPHENO_REMOTE_III_DB_PATH for this run",
    )
    parser.add_argument(
        "--folders",
        help="Comma-separated subfolders to sync (overrides FASTPHENO_SYNC_FOLDERS)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync entire remote root (legacy full-tree behaviour)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show files that would be downloaded without writing",
    )
    args = parser.parse_args()

    if args.list_remote:
        list_remote(args.remote_path, depth=1)
        print("\nDefault sync folders:", ", ".join(DEFAULT_SYNC_FOLDERS))
        return

    cfg = get_remote_config()
    if not cfg["host"]:
        print("Set FASTPHENO_REMOTE_HOST in backend/.env", file=sys.stderr)
        sys.exit(1)

    folder_override = None
    if args.folders:
        folder_override = [f.strip() for f in args.folders.split(",") if f.strip()]

    sync(
        dry_run=args.dry_run,
        remote_path=args.remote_path,
        folders=folder_override,
        sync_all=args.all,
    )


if __name__ == "__main__":
    main()
