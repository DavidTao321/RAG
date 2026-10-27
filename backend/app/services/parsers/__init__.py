"""文档解析器：按扩展名分发到对应 parser，统一返回纯文本。"""
from .docx_parser import parse_docx
from .excel_parser import parse_excel
from .pdf_parser import parse_pdf
from .text_parser import parse_text

PARSERS = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "xlsx": parse_excel,
    "txt": parse_text,
    "md": parse_text,
}


def parse_file(path: str, file_type: str) -> str:
    parser = PARSERS.get(file_type)
    if parser is None:
        raise ValueError(f"不支持的文件类型: {file_type}")
    text = parser(path)
    if not text or not text.strip():
        raise ValueError("解析结果为空：文件可能损坏或为纯图片内容")
    return text
