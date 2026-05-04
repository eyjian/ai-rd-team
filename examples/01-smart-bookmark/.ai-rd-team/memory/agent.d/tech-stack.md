---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [tech-stack]
estimated_tokens: 80
---

# SmartBookmark 技术栈

- **语言**：Python 3.10+
- **依赖**：仅标准库（不用 requests / click 等第三方包）
- **测试**：pytest（已作为 dev dep）
- **代码风格**：遵循 `python-best-practices` Skill

## 要求

- 所有函数带类型注解
- 文件头 `from __future__ import annotations`
- 用 `dataclasses` 定义数据模型
- 用 `pathlib.Path` 操作路径
- JSON 存储用 `json.dump(indent=2, ensure_ascii=False)` 保持可读
