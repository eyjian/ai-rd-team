"""Hello 模块 - M1 真实端到端验证"""


def hello(name: str) -> str:
    """返回 f'Hello, {name}!' 格式的问候字符串。

    Args:
        name: 被问候者的名字。

    Returns:
        格式为 "Hello, {name}!" 的问候字符串。
    """
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(hello("world"))
