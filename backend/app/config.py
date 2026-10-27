"""全局配置：pydantic-settings 从 .env / 环境变量读取。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # ===== 服务 =====
    app_name: str = "企业级 RAG 知识库问答系统"
    host: str = "127.0.0.1"
    port: int = 8000

    # ===== MySQL =====
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "rag_app"
    mysql_password: str = ""  # 必须在 .env 配置，不留弱默认值
    mysql_db: str = "rag_kb"

    # ===== JWT =====
    jwt_secret: str = ""  # 必须在 .env 配置随机密钥，main.py 启动时校验
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # ===== DashScope 通义千问 =====
    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v3"
    rerank_model: str = "qwen3-rerank"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ===== RAG 参数 =====
    chunk_size: int = 600
    chunk_overlap: int = 80
    retrieval_top_k: int = 10
    rrf_k: int = 60
    rerank_top_n: int = 5
    rerank_score_threshold: float = 0.1
    context_history_rounds: int = 4

    # ===== 语义缓存 =====
    redis_url: str = ""  # 留空 → 自动降级内存缓存
    cache_ttl_hours: int = 24
    cache_similarity_threshold: float = 0.92

    # ===== 限流 =====
    chat_rate_limit: str = "20/minute"
    login_rate_limit: str = "5/minute"  # 登录防爆破（未认证请求按 IP 限流）
    register_rate_limit: str = "10/minute"

    # ===== 安全 =====
    bcrypt_rounds: int = 12
    admin_username: str = "admin"
    admin_password: str = ""  # 必须在 .env 配置强密码，seeds.py 为空时拒绝建号

    # ===== 路径 =====
    data_dir: Path = BACKEND_DIR / "data"
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    chroma_dir: Path = BACKEND_DIR / "data" / "chroma"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


settings = Settings()
