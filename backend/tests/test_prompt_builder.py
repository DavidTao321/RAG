"""Prompt 组装：人设、引用编号上下文、历史消息拼接。"""
from app.services.rag.prompt_builder import (
    NO_CONTEXT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_context,
    build_messages,
    build_system_prompt,
)


def test_build_context_formats_refs():
    """引用片段转为 [n] 来源：文档名 + 内容的编号上下文。"""
    refs = [
        {"index": 1, "doc_name": "手机.xlsx", "content": "电池 5800mAh"},
        {"index": 2, "doc_name": "售后.docx", "content": "七天无理由"},
    ]
    ctx = build_context(refs)
    assert "[1] 来源：手机.xlsx\n电池 5800mAh" in ctx
    assert "[2] 来源：售后.docx\n七天无理由" in ctx


def test_build_system_prompt_contains_persona_and_context():
    sp = build_system_prompt("【内容】")
    assert sp.startswith(SYSTEM_PROMPT)
    assert sp.endswith("【参考资料】\n【内容】")


def test_build_messages_with_refs():
    """有引用：system 为人设 + 参考资料，历史消息按序插入，问题在末尾。"""
    msgs = build_messages(
        "电池多大",
        [{"index": 1, "doc_name": "d", "content": "c"}],
        [("user", "你好"), ("assistant", "你好！")],
    )
    assert msgs[0]["role"] == "system"
    assert "【参考资料】" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "你好"}
    assert msgs[2] == {"role": "assistant", "content": "你好！"}
    assert msgs[3] == {"role": "user", "content": "电池多大"}


def test_build_messages_without_refs_uses_no_context_prompt():
    """无引用：使用无上下文人设，消息只有 system + 当前问题。"""
    msgs = build_messages("你是谁", [], [])
    assert msgs[0] == {"role": "system", "content": NO_CONTEXT_SYSTEM_PROMPT}
    assert msgs[1] == {"role": "user", "content": "你是谁"}
