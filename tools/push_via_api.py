#!/usr/bin/env python3
"""push_via_api.py —— 用 GitHub Git Data API 提交文件（git push 不通时的兜底）

来源：2026-10-08 auto2768 经验回流实战。当时 `git push` 对 github.com:443
完全不通（`Connection was reset` / `Could not connect`，重试 20+ 次无效），
而 **api.github.com 可达**。改用 Git Data API 后一次成功。

它回答一个问题：**在只有 API 可达的网络下，如何把文件提交到远端仓库？**

原理（五步，本质是把 git 的本地对象写入搬到服务端做）：
  1) GET   refs/heads/<branch>            -> head commit sha
  2) GET   git/commits/<head>             -> base tree sha
  3) POST  git/blobs                      -> 每个文件的 blob sha（base64 内容）
  4) POST  git/trees（base_tree + entries）-> 新 tree sha
  5) POST  git/commits（parents=[head]）   -> 新 commit sha
     PATCH refs/heads/<branch>            -> 指向新 commit

认证**完全依赖已登录的 gh CLI**（`gh auth status` 应为 ✓）。
本脚本不接收、不存储、不打印任何凭据；请勿把 token 写进参数或 remote URL。

## 并发安全（多会话同时回流时必须）

上面的 5 步是 **read-modify-write**。两个会话同时跑时，双方可能读到同一个
head，各自基于同一个 base_tree 建树；后提交者的树**不含先提交者的改动**，
却把引用指向自己的 commit。结果是先提交者的改动在提交图上看"接在后面"，
**内容却被静默回退** —— 没有报错，只有数据消失。

因此本脚本采用 **compare-and-swap 重试**：每次尝试都重新读取 head 与
base_tree 并重建整棵树；引用更新失败（他人已前移）即退避重试。
配合下方"多会话使用建议"，可安全并发。

注意：CAS 只保证**不同文件的改动不会丢**。若两个会话改了**同一个文件的同一段**
（典型：都想追加下一条 Lxx），后提交者仍会覆盖前者 —— 这是语义冲突，
不是本工具能解决的，需要靠"先拉最新定编号 + 提交后回读查重"。

用法：
  # 提交若干文件
  python push_via_api.py --repo baimocn/autoresearch-sop --branch master \\
      --message-file msg.txt SKILL.md references/field-lessons.md tools/x.py

  # 演练：只打印将要执行的动作，不写入
  python push_via_api.py --repo owner/name --branch master --dry-run SKILL.md

  # 提交后自动核对远端文件大小（推荐）
  python push_via_api.py ... --verify

  # 多会话并发：加大重试（默认 5 次已够；文件多/网络慢可调大）
  python push_via_api.py ... --retries 10

  # 先看远端最新内容（定编号用，避免重复）
  python push_via_api.py --repo owner/name --branch master --show references/field-lessons.md

  # 只读自检：确认 api.github.com 与 gh 认证可用
  python push_via_api.py --repo owner/name --branch master --selftest

退出码：0=成功；1=任一步 API 失败；2=参数或环境问题（含 gh 未登录）。
"""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# 引用更新失败的常见特征：他人已前移 -> 可重试
RETRYABLE_REF_ERRORS = ("fast forward", "422", "does not match", "already exists")


def gh(method, path, body=None, timeout=180):
    """调用 gh api。返回 (parsed_json_or_text, error_str)。

    只用 gh CLI 自身的认证，不接触凭据文件。
    """
    cmd = ["gh", "api", "-X", method, path]
    payload = None
    if body is not None:
        payload = json.dumps(body)
        cmd += ["--input", "-"]
    try:
        p = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout)
    except FileNotFoundError:
        return None, "gh CLI 未安装（请先安装并 gh auth login）"
    except subprocess.TimeoutExpired:
        return None, f"超时 {timeout}s"
    if p.returncode != 0:
        return None, ((p.stderr or "") + (p.stdout or "")).strip()[:500]
    text = (p.stdout or "").strip()
    if not text:
        return {}, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return text, None


def check_env(repo):
    """环境自检：gh 是否登录 + api.github.com 是否可达 + 仓库是否可见。"""
    p = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    blob = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0 or "Logged in" not in blob:
        print("  !! gh 未登录或凭据失效 —— 请先 `gh auth login`")
        return False
    print("  OK gh 已登录")
    data, err = gh("GET", f"repos/{repo}")
    if err:
        print(f"  !! 仓库不可达 {repo}: {err}")
        return False
    print(f"  OK 仓库可达: {repo} (default_branch={data.get('default_branch')})")
    return True


def resolve_branch(repo, branch):
    if branch:
        return branch
    data, err = gh("GET", f"repos/{repo}")
    if err:
        return None
    return data.get("default_branch", "master")


def show_remote(repo, branch, path):
    """打印远端文件内容（用于定编号，避免重复）。"""
    info, err = gh("GET", f"repos/{repo}/contents/{path}?ref={branch}")
    if err:
        print(f"!! 读取远端失败 {path}: {err}")
        return EXIT_FAIL
    try:
        text = base64.b64decode(info["content"]).decode("utf-8")
    except Exception as exc:                                   # noqa: BLE001
        print(f"!! 解码失败: {type(exc).__name__}: {exc}")
        return EXIT_FAIL
    print(f"# ---- {repo}@{branch}:{path}  ({info.get('size')} B) ----")
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return EXIT_OK


def main():
    ap = argparse.ArgumentParser(
        description="用 GitHub Git Data API 提交文件（git push 不通时的兜底；并发安全）")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--branch", default=None, help="目标分支；省略则用仓库默认分支")
    ap.add_argument("--message", help="提交信息（与 --message-file 二选一）")
    ap.add_argument("--message-file", type=Path, help="提交信息的文件路径（推荐长信息用）")
    ap.add_argument("--dry-run", action="store_true", help="只演练，不写入远端")
    ap.add_argument("--verify", action="store_true", help="提交后核对远端文件大小")
    ap.add_argument("--selftest", action="store_true", help="只做环境自检并退出")
    ap.add_argument("--show", metavar="PATH", help="打印远端某个文件的内容后退出")
    ap.add_argument("--retries", type=int, default=5,
                    help="引用竞争时的重试次数（默认 5）")
    ap.add_argument("--assume-head", metavar="SHA", default=None,
                    help="调试用：强制首次尝试使用该 head，用于复现并发冲突")
    ap.add_argument("files", nargs="*", help="要提交的文件路径（相对当前目录）")
    args = ap.parse_args()

    print("=" * 72)
    print("GitHub API 推送（Git Data API 兜底；并发安全；不接触任何凭据）")
    print("=" * 72)

    if not check_env(args.repo):
        return EXIT_USAGE

    branch = resolve_branch(args.repo, args.branch)
    if not branch:
        print("!! 无法确定默认分支")
        return EXIT_USAGE
    print(f"  · 目标分支: {branch}")

    if args.selftest:
        print("\n自检通过：可以用 API 方式提交。")
        return EXIT_OK

    if args.show:
        return show_remote(args.repo, branch, args.show)

    # 提交信息
    if args.message_file:
        if not args.message_file.is_file():
            print(f"!! 提交信息文件不存在: {args.message_file}")
            return EXIT_USAGE
        message = args.message_file.read_text(encoding="utf-8")
    elif args.message:
        message = args.message
    else:
        print("!! 需要 --message 或 --message-file")
        return EXIT_USAGE
    print(f"  · 提交信息: {message.strip().splitlines()[0][:70]}")

    # 文件清单（内容在每次尝试时重新读取，确保拿到磁盘最新）
    if not args.files:
        print("!! 未指定任何文件")
        return EXIT_USAGE
    for f in args.files:
        if not Path(f).is_file():
            print(f"!! 文件不存在: {f}")
            return EXIT_USAGE

    if args.dry_run:
        items = [(Path(f).as_posix(), Path(f).read_bytes()) for f in args.files]
        total = sum(len(b) for _, b in items)
        print(f"  · 文件 {len(items)} 个，共 {total} 字节")
        print("\n[dry-run] 将执行：取 head -> 取 base tree -> 建 blob -> 建 tree -> 建 commit -> 更新 ref")
        print("[dry-run] 引用更新失败会自动重试（并发安全）")
        for name, b in items:
            print(f"    + {name}  ({len(b)} B)")
        print("\n[dry-run] 未写入任何远端内容。")
        return EXIT_OK

    # ---- 提交：compare-and-swap 重试 ----
    blob_cache = {}
    newc_sha = None
    for attempt in range(1, max(1, args.retries) + 1):
        if attempt > 1:
            print(f"\n--- 第 {attempt} 次尝试（引用已被他人前移，重新读取基线）---")

        # 每轮重新读取文件内容
        items = [(Path(f).as_posix(), Path(f).read_bytes()) for f in args.files]
        if attempt == 1:
            total = sum(len(b) for _, b in items)
            print(f"  · 文件 {len(items)} 个，共 {total} 字节")

        # 1) head（--assume-head 仅用于复现冲突）
        if attempt == 1 and args.assume_head:
            head_sha = args.assume_head
            print(f"  1/5 head      = {head_sha[:8]}  [assume-head 调试]")
        else:
            ref, err = gh("GET", f"repos/{args.repo}/git/refs/heads/{branch}")
            if err:
                print(f"!! 读取分支失败: {err}")
                return EXIT_FAIL
            head_sha = ref["object"]["sha"]
            print(f"  1/5 head      = {head_sha[:8]}")

        # 2) base tree
        commit, err = gh("GET", f"repos/{args.repo}/git/commits/{head_sha}")
        if err:
            print(f"!! 读取 head commit 失败: {err}")
            return EXIT_FAIL
        base_tree = commit["tree"]["sha"]
        print(f"  2/5 base_tree = {base_tree[:8]}")

        # 3) blobs（内容寻址，可跨轮复用）
        entries = []
        blob_fail = False
        for name, raw in items:
            key = hashlib.sha256(raw).hexdigest()
            sha = blob_cache.get(key)
            if sha is None:
                blob, err = gh("POST", f"repos/{args.repo}/git/blobs",
                               {"content": base64.b64encode(raw).decode("ascii"),
                                "encoding": "base64"})
                if err:
                    print(f"!! 建 blob 失败 {name}: {err}")
                    blob_fail = True
                    break
                sha = blob["sha"]
                blob_cache[key] = sha
            entries.append({"path": name, "mode": "100644", "type": "blob", "sha": sha})
        if blob_fail:
            return EXIT_FAIL
        print(f"  3/5 blobs     {len(entries)} 个（复用 {len(blob_cache) - 0} 缓存项）")
        for e in entries:
            print(f"        {e['path']:44} {e['sha'][:8]}")

        # 4) tree
        tree, err = gh("POST", f"repos/{args.repo}/git/trees",
                       {"base_tree": base_tree, "tree": entries})
        if err:
            print(f"!! 建 tree 失败: {err}")
            return EXIT_FAIL
        print(f"  4/5 tree      = {tree['sha'][:8]}")

        # 5) commit + ref（引用更新是唯一的 CAS 点）
        cand, err = gh("POST", f"repos/{args.repo}/git/commits",
                       {"message": message, "tree": tree["sha"], "parents": [head_sha]})
        if err:
            print(f"!! 建 commit 失败: {err}")
            return EXIT_FAIL

        upd, err = gh("PATCH", f"repos/{args.repo}/git/refs/heads/{branch}",
                      {"sha": cand["sha"], "force": False})
        if not err:
            newc_sha = cand["sha"]
            print(f"  5/5 commit    = {newc_sha[:8]}  ->  {branch} 已更新")
            break

        # 引用更新失败：区分"他人前移（可重试）"与"真失败"
        retryable = any(sig in err.lower() for sig in RETRYABLE_REF_ERRORS)
        print(f"  ~ 引用更新失败: {err[:200]}")
        if not retryable:
            print("    （非并发类错误，不重试）")
            return EXIT_FAIL
        if attempt >= max(1, args.retries):
            print(f"!! 重试 {args.retries} 次仍未成功；他人持续在提交，请稍后再试。")
            return EXIT_FAIL
        backoff = min(2 ** attempt, 15)
        print(f"    -> {backoff}s 后重试（并发冲突，重新读取 head 与 base_tree）")
        time.sleep(backoff)

    if not newc_sha:
        print("!! 未能完成提交")
        return EXIT_FAIL

    # ---- 验证远端（不要只信本地返回码）----
    print("\n-- 验证远端（不要只信本地返回码）--")
    latest, err = gh("GET", f"repos/{args.repo}/commits?sha={branch}&per_page=1")
    if err:
        print(f"  ~ 无法读取远端提交列表: {err}")
    else:
        top = latest[0]
        print(f"  OK 远端 HEAD = {top['sha'][:8]} | {top['commit']['message'].splitlines()[0][:60]}")
        if top["sha"] != newc_sha:
            print("  !! 远端 HEAD 与本地产出的 commit 不一致，请人工核对")

    if args.verify:
        print("\n-- 逐文件核对远端大小 --")
        bad = 0
        for name, raw in items:
            info, err = gh("GET", f"repos/{args.repo}/contents/{name}?ref={branch}")
            if err:
                print(f"  !! {name}: 读取失败 {err}")
                bad += 1
                continue
            remote_size = info.get("size")
            mark = "OK" if remote_size == len(raw) else "!!"
            if remote_size != len(raw):
                bad += 1
            print(f"  {mark} {name:44} 本地 {len(raw):7} / 远端 {remote_size}")
        if bad:
            print(f"\n!! {bad} 个文件大小不一致，请人工核对")
            return EXIT_FAIL

    print("\n完成。")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
