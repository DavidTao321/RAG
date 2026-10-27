"""启动入口。Windows 下必须单 worker（Chroma 嵌入式 SQLite 锁限制）。

开发：python run.py
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
