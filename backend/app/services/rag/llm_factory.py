"""DashScope 通义千问模型工厂（懒加载单例）。

LangChain 1.x 通过 langchain-openai 的 ChatOpenAI/OpenAIEmbeddings 走
阿里云 OpenAI 兼容模式（base_url=https://dashscope.aliyuncs.com/compatible-mode/v1）。
注意：百炼已弃用 max_tokens 参数，生成调用中不要传。
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ...config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        streaming=True,
        stream_usage=True,  # 流末 chunk 携带 usage_metadata
        temperature=0.3,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        dimensions=1024,
        # langchain-openai 1.7 默认启用客户端分词（发 token ID + base64），
        # 百炼兼容端点不识别，必须关闭以发送纯文本
        check_embedding_ctx_length=False,
    )
