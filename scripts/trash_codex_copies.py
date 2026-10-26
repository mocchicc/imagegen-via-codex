#!/usr/bin/env python3
"""Codex が ~/.codex/generated_images/<会話の ID>/ に残す画像の写しのうち、
指定先に保存した画像と中身（sha256）がまったく同じものだけを、macOS のゴミ箱へ移す。

`codex exec --ephemeral` でも、この写しだけは残る（2026-10-26、Codex CLI 0.160 で確認）。
中身が同じものしか動かさないので、保存していない絵（Codex が1回の中で作り直した絵など）や、
ほかのプロジェクトの写しには触らない。消さずにゴミ箱へ移すだけで、ゴミ箱を空にするのは利用者。

  python3 trash_codex_copies.py --session <会話の ID> /path/to/saved.png   # 1回分（codex exec が最初に出す session id）
  python3 trash_codex_copies.py /path/to/images-folder                       # まとめて作ったあと：写し全体から探す
  python3 trash_codex_copies.py --dry-run /path/to/images-folder             # 移さずに数えるだけ

- 保存先にはファイルかフォルダを渡す（フォルダは中を全部たどる）。Python 3 の標準の部品だけで動く
- Codex の置き場所は環境変数 CODEX_HOME（なければ ~/.codex）
"""
import argparse
import hashlib
import os
import pathlib
import shutil
import sys
import time

EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def saved_files(paths):
    for p in map(pathlib.Path, paths):
        if p.is_file():
            yield p
        elif p.is_dir():
            for root, _, names in os.walk(p):
                for name in names:
                    if pathlib.Path(name).suffix.lower() in EXTS:
                        yield pathlib.Path(root) / name
        else:
            sys.exit(f"見つからない: {p}")


def main():
    ap = argparse.ArgumentParser(description="Codex の画像の写しのうち、保存先と中身が同じものだけをゴミ箱へ移す")
    ap.add_argument("saved", nargs="+", help="保存した画像のファイルかフォルダ")
    ap.add_argument("--session", action="append", default=[], help="この会話の写しだけを見る（何度でも指定できる）")
    ap.add_argument("--dry-run", action="store_true", help="移さずに数えるだけ")
    a = ap.parse_args()

    root = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex")) / "generated_images"
    if not root.is_dir():
        sys.exit(f"写しの置き場所がない: {root}")
    trash = pathlib.Path.home() / ".Trash"
    if not a.dry_run and not trash.is_dir():
        sys.exit("ゴミ箱（~/.Trash）が見つからないので、何も移していません。--dry-run で数え、片付けは利用者に任せてください")

    # 保存した画像の指紋。写しは大きさが同じものだけ指紋を取る（写し全体は何GBにもなるので）
    saved = list(saved_files(a.saved))
    sizes = {p.stat().st_size for p in saved}
    hashes = {sha256(p) for p in saved}
    folders = [root / s for s in a.session] if a.session else sorted(d for d in root.iterdir() if d.is_dir())

    dest = trash / f"codex-generated-images-{time.strftime('%Y%m%d')}"
    moved = kept = moved_bytes = 0
    for folder in folders:
        moved_here = 0
        if not folder.is_dir():
            print(f"写しのフォルダがない: {folder.name}")
            continue
        for f in sorted(folder.iterdir()):
            if not f.is_file():
                continue
            same = f.stat().st_size in sizes and sha256(f) in hashes
            if not same:
                kept += 1
                if a.session:
                    print(f"残す（保存先に同じ中身がない）: {f}")
                continue
            moved += 1
            moved_here += 1
            moved_bytes += f.stat().st_size
            if not a.dry_run:
                (dest / folder.name).mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dest / folder.name / f.name))
        if not a.dry_run and moved_here and not any(folder.iterdir()):
            folder.rmdir()          # 写しを移して空になったフォルダだけ外す（ほかの空のフォルダには触らない）
    verb = "移せる" if a.dry_run else f"ゴミ箱（{dest}）へ移した"
    print(f"{verb}写し {moved} 枚（{moved_bytes / 1e6:.1f} MB）・保存先に同じ中身がないので残した写し {kept} 枚（ほかの作業の写しも数える）")


if __name__ == "__main__":
    main()
