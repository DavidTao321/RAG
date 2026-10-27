"""Git Commit 质量门禁工具：mark / status / check 三个子命令 + hook 模式。

设计：
- 标记文件 .claude/gates/<gate>.json（目录已 gitignore，不入库）记录检查通过时的
  code_state（HEAD + 所有 git 可见文件的内容哈希）——检查通过后代码动过一个字节，
  标记立即过期，杜绝「几小时前测过就放行」的假门禁
- 门禁判定：unit-test 与 quality 两个标记均为 pass 且 code_state 与当前工作区一致
  → 放行（exit 0）；否则 exit 2（Claude Code PreToolUse 的拦截语义：exit 2 阻止，
  stderr 作为原因展示；exit 1 是不拦截的错误，不能用）

用法：
  python gate_utils.py mark <unit-test|quality> <pass|fail> [--details "..."]
  python gate_utils.py status                    # 人类可读查看两个标记
  python gate_utils.py check                     # 手工验证门禁判定（不通过 exit 2）
  echo '<hook json>' | python gate_utils.py      # hook 模式（无参数且 stdin 有 JSON）
  python gate_utils.py post                      # PostToolUse 模式：git push 成功后作废旧标记
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GATES_DIR = PROJECT_ROOT / ".claude" / "gates"
GATES = ("unit-test", "quality")

# 保守匹配：git / git.exe 后跟（同一行内不含 ; & | 的任意内容）commit；
# 会误拦 git log --grep commit 这类命令，但门禁宁可误拦不可漏拦
_COMMIT_RE = re.compile(r"(?<![\w.-])git(?:\.exe)?\b[^\n;&|]*\bcommit\b")
_PUSH_RE = re.compile(r"(?<![\w.-])git(?:\.exe)?\b[^\n;&|]*\bpush\b")

# 推送成功特征（响应文本）/ 失败特征：两者都满足时才作废标记，宁可留旧标记也不误删
_PUSH_OK_RE = re.compile(r"->|\* \[new branch\]|up[- ]to[- ]date", re.I)
_PUSH_FAIL_RE = re.compile(r"fatal|rejected|error|denied|failed|could not", re.I)


def _utf8() -> None:
    """Windows 控制台默认 GBK，强制三个标准流用 UTF-8，避免中文原因乱码。"""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _git(*args: str) -> str:
    """只读 git 查询（stdout 文本）；禁用分页与凭据交互，防止 hook 挂起。"""
    env = dict(os.environ, GIT_PAGER="cat", GIT_TERMINAL_PROMPT="0")
    proc = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout


def compute_code_state() -> str:
    """HEAD + 全部 git 可见文件（已跟踪 + 未跟踪未忽略）的 路径+内容 哈希。

    .claude/gates 被 .gitignore 排除，标记文件自身不参与；.env 等忽略项同样不参与。
    首次提交（无 HEAD）时 HEAD 记 EMPTY。
    """
    h = hashlib.sha256()
    head = _git("rev-parse", "--verify", "HEAD").strip()
    h.update(("HEAD:" + (head or "EMPTY") + "\n").encode("utf-8"))
    tracked = _git("ls-files", "-z").split("\0")
    untracked = _git("ls-files", "-z", "--others", "--exclude-standard").split("\0")
    for path in sorted(p for p in (*tracked, *untracked) if p):
        h.update((path + "\0").encode("utf-8"))
        try:
            h.update((PROJECT_ROOT / path).read_bytes())
        except OSError:
            h.update(b"<unreadable>")
        h.update(b"\0")
    return h.hexdigest()


def _marker_path(gate: str) -> Path:
    return GATES_DIR / f"{gate}.json"


def _read_marker(gate: str) -> dict | None:
    try:
        return json.loads(_marker_path(gate).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cmd_mark(gate: str, status: str, details: str) -> int:
    if gate not in GATES:
        print(f"未知门禁: {gate}（可选 {', '.join(GATES)}）", file=sys.stderr)
        return 2
    if status not in ("pass", "fail"):
        print("status 只能是 pass / fail", file=sys.stderr)
        return 2
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    marker = {
        "gate": gate,
        "status": status,
        "details": details,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_state": compute_code_state(),
        "head": _git("rev-parse", "--verify", "HEAD").strip() or "EMPTY",
    }
    _marker_path(gate).write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写入 {gate} 标记: {status}（{details}）")
    return 0


def gate_problems() -> list[str]:
    """返回拦截原因列表；空列表 = 放行。"""
    current = compute_code_state()
    problems = []
    for gate in GATES:
        m = _read_marker(gate)
        if m is None:
            problems.append(f"缺少「{gate}」通过标记（请运行 /gitcommit-agent 完成检查）")
            continue
        if m.get("status") != "pass":
            problems.append(f"「{gate}」检查未通过：{m.get('details', '无详情')}")
            continue
        if m.get("code_state") != current:
            problems.append(f"「{gate}」标记已过期（检查通过后代码有改动，需重新检查）")
    return problems


def cmd_status() -> int:
    current = compute_code_state()
    for gate in GATES:
        m = _read_marker(gate)
        if m is None:
            print(f"{gate}: 无标记")
            continue
        fresh = "新鲜" if m.get("code_state") == current else "已过期"
        print(f"{gate}: {m['status']}（{fresh}）{m.get('at', '')} {m.get('details', '')}")
    return 0


def cmd_check() -> int:
    problems = gate_problems()
    if not problems:
        print("门禁通过：unit-test 与 quality 标记均有效")
        return 0
    for p in problems:
        print(p, file=sys.stderr)
    print("门禁拦截：未通过质量门禁", file=sys.stderr)
    return 2


def _deny_json(reason: str) -> str:
    """stdout 输出结构化 deny：子代理内 exit 2 可能被忽略的版本上仍能阻止。"""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        ensure_ascii=False,
    )


def hook_mode() -> int:
    """Claude Code PreToolUse 调用：stdin 传入工具调用 JSON。"""
    if sys.stdin.isatty():
        return 0  # 手动无参运行，非 hook 调用
    try:
        payload = json.loads(sys.stdin.read())
        command = str(payload.get("tool_input", {}).get("command", ""))
    except Exception:
        return 0  # 拿不到命令内容就不拦（此时也识别不了 commit，放行）
    if not _COMMIT_RE.search(command):
        return 0  # 非 commit 命令直接放行，不拖慢每次 Bash
    # commit 类命令：门禁判定，脚本自身异常一律 fail-closed（不能让提交漏网）
    try:
        problems = gate_problems()
    except Exception as e:  # noqa: BLE001
        problems = [f"门禁脚本异常（fail-closed）: {e}"]
    if not problems:
        return 0
    reason = (
        "git commit 被质量门禁拦截：\n- "
        + "\n- ".join(problems)
        + "\n请先运行 /gitcommit-agent 完成单元测试与质量检查，通过后再存档。"
    )
    print(reason, file=sys.stderr)
    print(_deny_json(reason))
    return 2


def cmd_post() -> int:
    """PostToolUse 模式：git push 成功（已上传远程）后立即删除旧门禁标记。

    标记在 commit 后本已随 HEAD 变化过期，这里按用户要求物理作废——
    通行证用一次就烧掉，下次存档必须重新检查。
    """
    if sys.stdin.isatty():
        return 0
    try:
        payload = json.loads(sys.stdin.read())
        command = str(payload.get("tool_input", {}).get("command", ""))
        response = payload.get("tool_response", {})
    except Exception:
        return 0
    if not _PUSH_RE.search(command):
        return 0
    text = json.dumps(response, ensure_ascii=False)
    # 响应里没有成功特征、或有失败特征 → 推送未成功，标记保留（保守，不误删）
    if _PUSH_FAIL_RE.search(text) or not _PUSH_OK_RE.search(text):
        return 0
    deleted = sorted(p.name for p in GATES_DIR.glob("*.json") if p.is_file())
    for name in deleted:
        (GATES_DIR / name).unlink()
    if deleted:
        print(f"推送成功，已作废旧门禁标记：{', '.join(deleted)}（下次存档需重新检查）")
    return 0


def main() -> int:
    _utf8()
    args = sys.argv[1:]
    if not args:
        return hook_mode()
    if args[0] == "mark" and len(args) >= 3:
        details = args[args.index("--details") + 1] if "--details" in args else ""
        return cmd_mark(args[1], args[2], details)
    if args[0] == "status":
        return cmd_status()
    if args[0] == "check":
        return cmd_check()
    if args[0] == "post":
        return cmd_post()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
