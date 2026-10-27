"""Excel 解析：读全部 sheet，每行转「列名：值；」键值对文本（电商参数表核心场景）。

处理要点：
- 合并单元格产生的 NaN 用 forward-fill 补全（保持列语义）
- 无表头时退化为整行拼接
- 每行输出一行文本，便于后续按行组分块
"""
import pandas as pd


def _row_to_text(columns: list[str], values: list) -> str:
    parts = []
    for col, val in zip(columns, values):
        if pd.isna(val):
            continue
        s = str(val).strip()
        if s:
            parts.append(f"{col}：{s}")
    return "；".join(parts)


def parse_excel(path: str) -> str:
    sheets = pd.read_excel(path, sheet_name=None, dtype=object)
    lines: list[str] = []
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        df = df.ffill()  # 合并单元格补全
        columns = [str(c).strip() for c in df.columns]
        has_header = all(c and not c.startswith("Unnamed") for c in columns)
        if not has_header:
            # 无表头：整行拼接
            for _, row in df.iterrows():
                text = " ".join(str(v).strip() for v in row if pd.notna(v))
                if text.strip():
                    lines.append(text.strip())
            continue
        lines.append(f"【{sheet_name}】")
        for _, row in df.iterrows():
            text = _row_to_text(columns, list(row))
            if text:
                lines.append(text)
    return "\n".join(lines)
