---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [contracts]
estimated_tokens: 60
---

# 本次任务接口契约

需要实现一个函数：

```python
def fibonacci(n: int) -> int:
    """返回第 n 个斐波那契数（n >= 0，fib(0)=0, fib(1)=1）。"""
```

- n < 0 抛 ValueError
- 使用迭代实现（不递归）
