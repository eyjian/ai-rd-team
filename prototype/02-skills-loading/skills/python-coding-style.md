# Python 编码规范（测试用 Skill）

## 命名规范

- 函数、变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员以 `_` 开头

## 类型注解（必须）

所有函数参数和返回值必须有类型注解：

```python
def add(a: int, b: int) -> int:
    return a + b
```

## 代码风格

- 缩进：4 空格
- 行长度：≤ 100 字符
- 字符串：优先使用双引号
- import 顺序：标准库 → 第三方 → 本项目
- 函数间空 2 行，类内方法间空 1 行

## 文档字符串

公开函数需有简短 docstring：

```python
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b
```

## 错误处理

- 显式抛业务异常，不吞异常
- 异常消息应包含上下文信息
