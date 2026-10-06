#!/usr/bin/env python3
"""Write a `docker load`-able image tar (scratch + static server + page) without a daemon.

Uses the classic `docker save` layout (manifest.json + layer.tar per layer), which
older Docker engines such as Synology Container Manager import without trouble.
"""

import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
PORT = "8080"


def tar_bytes(entries: list[tuple[str, bytes | None, int]], mtime: int) -> bytes:
    """Build an uncompressed tar from (path, data, mode) entries; data None means a directory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, data, mode in entries:
            info = tarfile.TarInfo(name)
            info.mode = mode
            info.mtime = mtime
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            if data is None:
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["amd64", "arm64"], required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--page", type=Path, required=True)
    parser.add_argument("--name", default="sound-tools")
    parser.add_argument("--tag", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    created = now.isoformat().replace("+00:00", "Z")
    mtime = int(now.timestamp())

    layers = [
        (
            "COPY server /server",
            tar_bytes([("server", args.server.read_bytes(), 0o755)], mtime),
        ),
        (
            "COPY 음향도구-통합.html /srv/index.html",
            tar_bytes(
                [
                    ("srv", None, 0o755),
                    ("srv/index.html", args.page.read_bytes(), 0o644),
                ],
                mtime,
            ),
        ),
    ]
    diff_ids = [f"sha256:{sha256(data)}" for _, data in layers]

    platform = {"architecture": args.arch, "os": "linux"}
    if args.arch == "arm64":
        platform["variant"] = "v8"
    container_config = {
        "User": "65534:65534",
        "ExposedPorts": {f"{PORT}/tcp": {}},
        "Env": [f"PORT={PORT}", "ROOT=/srv"],
        "Entrypoint": ["/server"],
        "WorkingDir": "/",
        "Healthcheck": {
            "Test": ["CMD", "/server", "healthcheck"],
            "Interval": 30_000_000_000,
            "Timeout": 5_000_000_000,
            "StartPeriod": 5_000_000_000,
            "Retries": 3,
        },
        "Labels": {
            "org.opencontainers.image.title": "음향 현장 도구",
            "org.opencontainers.image.description": "QSD v4 · View Point v1.3 · 케이블 판독기 · 스피커 리깅 v9.4",
            "org.opencontainers.image.created": created,
        },
    }
    config = {
        **platform,
        "created": created,
        "config": container_config,
        "rootfs": {"type": "layers", "diff_ids": diff_ids},
        "history": [{"created": created, "created_by": by} for by, _ in layers],
    }
    config_bytes = json.dumps(
        config, ensure_ascii=False, separators=(",", ":")
    ).encode()
    config_name = f"{sha256(config_bytes)}.json"

    files: list[tuple[str, bytes | None, int]] = [(config_name, config_bytes, 0o644)]
    layer_paths, parent = [], ""
    for (_, data), diff_id in zip(layers, diff_ids, strict=True):
        layer_id = sha256(f"{parent} {diff_id}".encode())
        legacy = {"id": layer_id, "created": created, "os": "linux"}
        if parent:
            legacy["parent"] = parent
        else:
            legacy["architecture"] = args.arch
        files += [
            (layer_id, None, 0o755),
            (f"{layer_id}/VERSION", b"1.0", 0o644),
            (f"{layer_id}/json", json.dumps(legacy).encode(), 0o644),
            (f"{layer_id}/layer.tar", data, 0o644),
        ]
        layer_paths.append(f"{layer_id}/layer.tar")
        parent = layer_id

    repo_tags = [f"{args.name}:{tag}" for tag in args.tag]
    manifest = [{"Config": config_name, "RepoTags": repo_tags, "Layers": layer_paths}]
    repositories = {args.name: dict.fromkeys(args.tag, parent)}
    files += [
        ("manifest.json", json.dumps(manifest).encode(), 0o644),
        ("repositories", json.dumps(repositories).encode(), 0o644),
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(tar_bytes(files, mtime))
    print(
        f"→ {args.out} ({args.out.stat().st_size / 1e6:.1f} MB) {', '.join(repo_tags)}"
    )


if __name__ == "__main__":
    main()
