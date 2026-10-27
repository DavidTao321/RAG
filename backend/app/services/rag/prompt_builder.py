"""Prompt 组装：电商客服人设 + 引用编号规则 + 参考资料上下文。"""

SYSTEM_PROMPT = """你是「慧购优选」电商平台的智能客服助手，专门回答用户关于商品的问题。

你的回答必须严格基于下方提供的【参考资料】，并遵守以下规则：
1. 每个事实性信息（商品参数、价格、售后政策等）末尾必须用 [n] 标注引用来源编号，n 是该信息所在参考资料的编号，例如"电池容量为 5000mAh[1]"；
2. 只能回答参考资料中明确包含的内容，禁止编造或推测；价格、优惠与售后政策必须逐字引用原文表述；
3. 如果参考资料不足以回答用户的问题，直接回答"抱歉，知识库中未包含该信息"，不要猜测；
4. 用简体中文回答，Markdown 排版，条理清晰、简洁友好；适当使用小标题与列表。

注意：[n] 只能引用【参考资料】中出现的编号，不得编造编号。"""

# 防御性保留：chat_service 在 refs 为空时提前返回兜底话术，正常流程走不到这里；
# 保留它保证 build_messages 单独使用（如测试）时也有安全的无上下文人设
NO_CONTEXT_SYSTEM_PROMPT = """你是「慧购优选」电商平台的智能客服助手。
当前没有检索到相关的商品知识库内容。如果用户问的是知识库中不存在的商品或信息，
请直接回答"抱歉，知识库中未包含该信息"，不要编造任何参数、价格或政策。"""


def build_system_prompt(context: str) -> str:
    return f"{SYSTEM_PROMPT}\n\n【参考资料】\n{context}"


def build_context(refs: list[dict]) -> str:
    """refs: [{"index","doc_name","content"}...] → 编号上下文文本。"""
    return "\n\n".join(f"[{r['index']}] 来源：{r['doc_name']}\n{r['content']}" for r in refs)


def build_messages(question: str, refs: list[dict], history: list[tuple[str, str]]) -> list[dict]:
    """组装完整消息列表：system(人设+参考资料) + 历史 + 当前问题。

    history 为 [(role, content)]，按时间正序，引用编号已在加载时剥离。
    """
    context = build_context(refs)
    system = build_system_prompt(context) if refs else NO_CONTEXT_SYSTEM_PROMPT
    messages: list[dict] = [{"role": "system", "content": system}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    return messages
