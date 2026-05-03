# 计算器接口设计文档

- 作者：陈架构（architect）
- 团队：proto-p1-team
- 日期：2026-05-03

## 1. 目标

提供一个简单、纯函数式的 Python 计算器接口，支持基础四则运算，错误处理明确，便于测试。

## 2. 接口签名

```python
def calc(op: str, a: float, b: float) -> float:
    ...
```

- 模块文件：`calculator.py`
- 函数名：`calc`
- 返回值：`float` 类型的运算结果

## 3. 参数说明

| 参数 | 类型  | 说明                             |
| ---- | ----- | -------------------------------- |
| op   | str   | 运算符，取值：`+`、`-`、`*`、`/` |
| a    | float | 左操作数                         |
| b    | float | 右操作数                         |

## 4. 行为规范

1. `op == "+"`：返回 `a + b`
2. `op == "-"`：返回 `a - b`
3. `op == "*"`：返回 `a * b`
4. `op == "/"`：
   - 若 `b == 0`，抛出 `ZeroDivisionError`，错误信息建议：`"division by zero"`
   - 否则返回 `a / b`
5. 其他任何 `op` 值：抛出 `ValueError`，错误信息建议：`f"unsupported operator: {op}"`

## 5. 错误处理约定

| 场景             | 异常类型            |
| ---------------- | ------------------- |
| 除数为 0         | `ZeroDivisionError` |
| 未知运算符       | `ValueError`        |

类型错误（如 `a`、`b` 非数值）不做额外校验，交由 Python 原生行为处理。

## 6. 示例

```python
calc("+", 1, 2)      # -> 3.0
calc("-", 5, 3)      # -> 2.0
calc("*", 4, 2.5)    # -> 10.0
calc("/", 10, 4)     # -> 2.5
calc("/", 1, 0)      # -> raises ZeroDivisionError
calc("%", 1, 2)      # -> raises ValueError
```

## 7. 非目标（本期不做）

- 不处理字符串形式的表达式解析
- 不支持一元运算、幂运算、取余
- 不做浮点精度控制（由调用方处理）

## 8. 测试建议（给 tester）

至少覆盖以下用例：

1. 四则运算各 1 条正向用例
2. 浮点数运算 1 条
3. 除零抛 `ZeroDivisionError`
4. 未知运算符抛 `ValueError`
