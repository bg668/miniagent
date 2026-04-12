from __future__ import annotations


def truncate(text: str, max_len: int = 80) -> str:
    value = " ".join(text.split())
    return value if len(value) <= max_len else value[: max_len - 3] + "..."


def markdown_table(rows: list[dict[str, str]], headers: list[str]) -> str:
    if not rows:
        return "暂无匹配结果。"
    header_line = "  ".join(headers)
    divider = "  ".join("-" * max(len(header), 8) for header in headers)
    body = []
    for row in rows:
        body.append("  ".join(row.get(header, "") for header in headers))
    return "\n".join([header_line, divider, *body])

