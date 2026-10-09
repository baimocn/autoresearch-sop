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

用法：
  # 提交若干文件
  python push_via_api.py --repo baimocn/autoresearch-sop --branch master \\
      --message-file msg.txt SKILL.md references/field-lessons.md tools/x.py

  # 演练：只打印将要执行的动作，不写入
  python push_via_api.py --repo owner/name --branch master --dry-run SKILL.md

  # 提交后自动核对远端文件大小（推荐）
  python push_via_api.py ... --verify

  # 只读自检：确认 api.github.com 与 gh 认证可用
  python push_via_api.py --repo owner/name --branch master --selftest

退出码：0=成功；1=任一步 API 失败；2=参数或环境问题（含 gh 未登录）。
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


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


def main():
    ap = argparse.ArgumentParser(
        description="用 GitHub Git Data API 提交文件（git push 不通时的兜底）")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--branch", default=None, help="目标分支；省略则用仓库默认分支")
    ap.add_argument("--message", help="提交信息（与 --message-file 二选一）")
    ap.add_argument("--message-file", type=Path, help="提交信息的文件路径（推荐长信息用）")
    ap.add_argument("--dry-run", action="store_true", help="只演练，不写入远端")
    ap.add_argument("--verify", action="store_true", help="提交后核对远端文件大小")
    ap.add_argument("--selftest", action="store_true", help="只做环境自检并退出")
    ap.add_argument("files", nargs="*", help="要提交的文件路径（相对当前目录）")
    args = ap.parse_args()

    print("=" * 72)
    print("GitHub API 推送（Git Data API 兜底；不接触任何凭据）")
    print("=" * 72)

    if not check_env(args.repo):
        return EXIT_USAGE
    if args.selftest:
        print("\n自检通过：可以用 API 方式提交。")
        return EXIT_OK

    # 分支
    branch = args.branch
    if not branch:
        data, err = gh("GET", f"repos/{args.repo}")
        if err:
            print(f"!! 无法确定默认分支: {err}")
            return EXIT_USAGE
        branch = data.get("default_branch", "master")
    print(f"  · 目标分支: {branch}")

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
    first_line = message.strip().splitlines()[0]
    print(f"  · 提交信息: {first_line[:70]}")

    # 待提交文件
    if not args.files:
        print("!! 未指定任何文件")
        return EXIT_USAGE
    items = []
    for f in args.files:
        path = Path(f)
        if not path.is_file():
            print(f"!! 文件不存在: {f}")
            return EXIT_USAGE
        items.append((path.as_posix(), path.read_bytes()))
    total = sum(len(b) for _, b in items)
    print(f"  · 文件 {len(items)} 个，共 {total} 字节")

    if args.dry_run:
        print("\n[dry-run] 将执行：取 head -> 取 base tree -> 建 blob -> 建 tree -> 建 commit -> 更新 ref")
        for name, b in items:
            print(f"    + {name}  ({len(b)} B)")
        print("\n[dry-run] 未写入任何远端内容。")
        return EXIT_OK

    # 1) head
    ref, err = gh("GET", f"repos/{args.repo}/git/refs/heads/{branch}")
    if err:
        print(f"!! 读取分支失败: {err}")
        return EXIT_FAIL
    head_sha = ref["object"]["sha"]
    print(f"\n  1/5 head      = {head_sha[:8]}")

    # 2) base tree
    commit, err = gh("GET", f"repos/{args.repo}/git/commits/{head_sha}")
    if err:
        print(f"!! 读取 head commit 失败: {err}")
        return EXIT_FAIL
    base_tree = commit["tree"]["sha"]
    print(f"  2/5 base_tree = {base_tree[:8]}")

    # 3) blobs
    entries = []
    for name, raw in items:
        blob, err = gh("POST", f"repos/{args.repo}/git/blobs",
                       {"content": base64.b64encode(raw).decode("ascii"),
                        "encoding": "base64"})
        if err:
            print(f"!! 建 blob 失败 {name}: {err}")
            return EXIT_FAIL
        entries.append({"path": name, "mode": "100644", "type": "blob",
                        "sha": blob["sha"]})
        print(f"  3/5 blob      {name:44} {blob['sha'][:8]}")

    # 4) tree
    tree, err = gh("POST", f"repos/{args.repo}/git/trees",
                   {"base_tree": base_tree, "tree": entries})
    if err:
        print(f"!! 建 tree 失败: {err}")
        return EXIT_FAIL
    print(f"  4/5 tree      = {tree['sha'][:8]}")

    # 5) commit + ref
    newc, err = gh("POST", f"repos/{args.repo}/git/commits",
                   {"message": message, "tree": tree["sha"], "parents": [head_sha]})
    if err:
        print(f"!! 建 commit 失败: {err}")
        return EXIT_FAIL
    upd, err = gh("PATCH", f"repos/{args.repo}/git/refs/heads/{branch}",
                  {"sha": newc["sha"], "force": False})
    if err:
        print(f"!! 更新分支引用失败: {err}")
        print("   提示：若因并发导致 ref 已前移，重新运行本脚本即可（会以新 head 为父提交）。")
        return EXIT_FAIL
    print(f"  5/5 commit    = {newc['sha'][:8]}  ->  {branch} 已更新")

    # 验证
    print("\n-- 验证远端（不要只信本地返回码）--")
    latest, err = gh("GET", f"repos/{args.repo}/commits?sha={branch}&per_page=1")
    if err:
        print(f"  ~ 无法读取远端提交列表: {err}")
    else:
        top = latest[0]
        print(f"  OK 远端 HEAD = {top['sha'][:8]} | {top['commit']['message'].splitlines()[0][:60]}")
        if top["sha"] != newc["sha"]:
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
