#!/usr/bin/env python3
"""Combine the latest sound tools from the speaker-rigging repo into one HTML file."""

import argparse
import datetime
import json
from pathlib import Path
import posixpath
import re
import subprocess
import unicodedata

HERE = Path(__file__).resolve().parent

QSD_REF = "origin/claude/gallant-davinci-3jr45t"
MAIN_REF = "origin/main"

TOOLS = [
    {
        "id": "qsd",
        "ref": QSD_REF,
        "path": "QSD-v4/index.html",
        "bundle": True,
        "name": "QSD 현장 배치 판단",
        "short": "QSD",
        "version": "v4",
        "desc": "공간과 가진 스피커로 덜 위험한 배치 후보와 판단 지도를 제안합니다. 얼라이먼트·엔드파이어·카디오이드 계산 포함.",
    },
    {
        "id": "viewpoint",
        "ref": MAIN_REF,
        "path": "View-Point-v1.3.html",
        "name": "View Point",
        "short": "View Point",
        "version": "v1.3",
        "desc": "카메라·LED·프롬프터가 객석 각 자리에서 실제로 어떻게 보이는지 미리 확인합니다.",
    },
    {
        "id": "cable",
        "ref": MAIN_REF,
        "path": "케이블판독기.html",
        "name": "케이블 판독기",
        "short": "케이블 판독기",
        "version": "",
        "desc": "스피커·전원·SDI·LAN 케이블 굵기와 차단기, 전기 연장 가능 여부를 판단합니다.",
    },
    {
        "id": "rigging",
        "ref": MAIN_REF,
        "path": "스피커-리깅-산정-v9.4.html",
        "name": "스피커 리깅 산정",
        "short": "스피커 리깅",
        "version": "v9.4",
        "desc": "총 무게와 포인트 수로 앵커·와이어·샤클 등 리깅 부품 규격을 산정합니다.",
    },
]


class Repo:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._trees: dict[str, dict[str, str]] = {}

    def git(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(self.path), *args], check=True, capture_output=True
        ).stdout

    def commit(self, ref: str) -> tuple[str, str]:
        out = self.git("log", "-1", "--format=%h %cs", ref).decode().split()
        return out[0], out[1]

    def read(self, ref: str, path: str) -> str:
        # File names committed from macOS are NFD; look them up by NFC form.
        if ref not in self._trees:
            names = self.git("ls-tree", "-r", "--name-only", "-z", ref).decode()
            self._trees[ref] = {
                unicodedata.normalize("NFC", n): n for n in names.split("\0") if n
            }
        real = self._trees[ref][unicodedata.normalize("NFC", path)]
        return self.git("show", f"{ref}:{real}").decode("utf-8")


def bundle_page(repo: Repo, ref: str, index_path: str) -> str:
    """Inline every local stylesheet and script referenced by index_path."""
    base = posixpath.dirname(index_path)
    html = repo.read(ref, index_path)

    def local(url: str) -> str:
        return posixpath.normpath(posixpath.join(base, url.split("?", 1)[0]))

    def inline_css(match: re.Match[str]) -> str:
        css = repo.read(ref, local(match.group(1)))
        if re.search(r"</style", css, re.IGNORECASE):
            raise ValueError(f"{match.group(1)} contains </style")
        return f"<style>\n{css}\n</style>"

    def inline_js(match: re.Match[str]) -> str:
        js = repo.read(ref, local(match.group(1)))
        if re.search(r"</script|<!--", js, re.IGNORECASE):
            raise ValueError(f"{match.group(1)} contains </script or <!--")
        return f"<script>\n{js}\n</script>"

    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="(?!https?:|data:)([^"]+)"\s*/?>',
        inline_css,
        html,
    )
    html = re.sub(
        r'<script\s+src="(?!https?:|data:)([^"]+)"\s*>\s*</script>', inline_js, html
    )
    leftover = re.findall(r'(?:src|href)="(?!https?:|data:|#)([^"]+)"', html)
    if leftover:
        raise ValueError(f"unresolved local references: {leftover}")
    return html


def embed(tool_id: str, html: str) -> str:
    # Escaping every "<" keeps the payload from ever closing its <script> early.
    payload = json.dumps(html, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/json" id="src-{tool_id}">{payload}</script>'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, required=True, help="speaker-rigging git checkout"
    )
    parser.add_argument(
        "--out", type=Path, default=HERE / "dist" / "음향도구-통합.html"
    )
    args = parser.parse_args()

    repo = Repo(args.repo)
    meta, blocks, origins = [], [], []
    for tool in TOOLS:
        if tool.get("bundle"):
            html = bundle_page(repo, tool["ref"], tool["path"])
        else:
            html = repo.read(tool["ref"], tool["path"])
        sha, date = repo.commit(tool["ref"])
        blocks.append(embed(tool["id"], html))
        meta.append({k: tool[k] for k in ("id", "name", "short", "version", "desc")})
        origins.append(f"{tool['path']} @ {sha} ({date})")
        print(f"  {tool['id']:<10} {len(html.encode()) / 1e6:5.2f} MB  {origins[-1]}")

    today = datetime.date.today().isoformat()
    build = {"date": today, "text": f"빌드 {today}", "sources": origins}

    page = (HERE / "launcher.html").read_text(encoding="utf-8")
    for marker, value in (
        ("/*TOOLS_META*/[]", json.dumps(meta, ensure_ascii=False)),
        ("/*BUILD_INFO*/{}", json.dumps(build, ensure_ascii=False)),
        ("<!--TOOL_SOURCES-->", "\n".join(blocks)),
    ):
        if page.count(marker) != 1:
            raise ValueError(f"launcher.html must contain {marker} exactly once")
        page = page.replace(marker, value)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"→ {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
