"""Word 解析：段落 + 表格（表格行转「表头：值」键值对）。"""
from docx import Document
from docx.table import Table


def _table_to_lines(table: Table) -> list[str]:
    lines = []
    for row in table.rows:
        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
        # 每行按「单元格1：单元格2；单元格3：单元格4；…」两两配对输出——
        # 商品参数表就是每行一对「名称：数值」的格式，配对后检索能命中具体参数
        text = "；".join(f"{cells[i]}：{cells[i + 1]}" for i in range(0, len(cells) - 1, 2))
        if len(cells) % 2 == 1:
            text = (text + "；" if text else "") + cells[-1]
        if text.strip():
            lines.append(text)
    return lines


def parse_docx(path: str) -> str:
    doc = Document(path)
    lines: list[str] = []
    for element in doc.element.body:
        tag = element.tag.split("}")[-1]
        if tag == "p":
            text = "".join(node.text or "" for node in element.iter() if node.tag.endswith("}t"))
            if text.strip():
                lines.append(text.strip())
    for table in doc.tables:
        lines.extend(_table_to_lines(table))
    return "\n".join(lines)
