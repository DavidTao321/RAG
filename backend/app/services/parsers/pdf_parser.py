"""PDF 解析：pdfplumber 优先（表格感知），失败回退 pypdf。"""
import pdfplumber


def parse_pdf(path: str) -> str:
    try:
        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                # 表格补充抽取
                for table in page.extract_tables():
                    for row in table:
                        if row and any(cell for cell in row if cell):
                            row_text = "；".join(
                                str(c).strip().replace("\n", " ") for c in row if c and str(c).strip()
                            )
                            if row_text:
                                text += "\n" + row_text
                if text.strip():
                    pages.append(text.strip())
        return "\n\n".join(pages)
    except Exception:  # noqa: BLE001 回退 pypdf
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
