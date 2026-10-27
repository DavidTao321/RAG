"""业务异常与统一错误响应。"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    """业务异常：status_code 为 HTTP 状态码，detail 为对外提示信息。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def not_found(detail: str = "资源不存在") -> BusinessError:
    return BusinessError(404, detail)


def forbidden(detail: str = "没有权限") -> BusinessError:
    return BusinessError(403, detail)


def conflict(detail: str) -> BusinessError:
    return BusinessError(409, detail)


def bad_request(detail: str) -> BusinessError:
    return BusinessError(400, detail)


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    return JSONResponse(status_code=422, content={"detail": f"参数错误: {first.get('msg', '')}"})
