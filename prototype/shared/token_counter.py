"""token 估算工具

由于 CodeBuddy 未暴露精确的 token API，本工具提供粗略估算。

估算规则（参考 OpenAI/Anthropic 经验）：
- 英文：约 1 token = 4 字符 = 0.75 word
- 中文：约 1 token = 1.5-2 字符
- 代码：约 1 token = 3 字符

本工具用于原型阶段对消息/制品的 token 数粗估，真实值会有 ±30% 偏差。
"""
from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """粗略估算一段文本的 token 数。

    规则：
    - 汉字（\u4e00-\u9fff）：每字约 1.7 token
    - 英文字母+数字：每 4 字符约 1 token
    - 其他（符号、空格等）：每 2 字符约 1 token
    """
    if not text:
        return 0

    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    alnum = len(re.findall(r"[A-Za-z0-9]", text))
    others = len(text) - chinese - alnum

    tokens = chinese / 1.7 + alnum / 4 + others / 2
    return int(tokens + 0.5)


def estimate_message_cost(
    content: str, msg_type: str = "message", recipients: int = 1
) -> dict:
    """估算一条消息的总 token 开销。

    包括：
    - 发送方产出消息的 output token
    - 接收方读取消息的 input token（广播时按接收者数量倍增）
    """
    base = estimate_tokens(content)
    if msg_type == "broadcast":
        return {
            "sender_output": base,
            "receiver_input_total": base * recipients,
            "total": base * (recipients + 1),
        }
    else:
        return {
            "sender_output": base,
            "receiver_input_total": base,
            "total": base * 2,
        }


def estimate_artifact_cost(content: str) -> int:
    """估算产出一个制品文件的 output token。"""
    return estimate_tokens(content)


if __name__ == "__main__":
    # 自测
    samples = [
        ("你好世界", 4),            # 预期：约 2-3 token
        ("Hello World", 2),
        ("def add(a, b):\n    return a + b", 8),
        ("项目经理：各位，我们接到一个新需求，请大家参与讨论", 15),
    ]
    print(f"{'文本':<40} {'估算 token':<10}")
    print("-" * 55)
    for text, expected in samples:
        est = estimate_tokens(text)
        preview = text[:30] + ("..." if len(text) > 30 else "")
        print(f"{preview:<40} {est:<10}")
