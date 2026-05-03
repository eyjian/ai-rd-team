# P4 结论：制品并发写

> 基于 `simulated/concurrent_write.py` 实测数据
> 日期：2026-05-03

## 测试结果

| 场景 | 结果 | 判定 |
|------|------|------|
| 10 线程写 10 个不同文件 | 全部成功，0 失败 | ✅ 完全安全 |
| 10 线程追加同一文件（无保护） | Python GIL 保护下可用，跨进程不可靠 | ⚠️ 不推荐 |
| 10 线程写同一文件 + 原子 rename | 最终内容完整，但是 last-write-wins | ✅ 适合单一状态 |
| 10 线程追加同一文件 + fcntl 锁 | 所有写入都保留 | ✅ 适合日志 |

## ai-rd-team 制品写入策略建议

### S1：不同文件并发写（**默认策略**）

**适用场景**：绝大多数制品产出
- 架构文档（由架构师独占）
- 代码文件（每个开发者负责不同文件）
- 测试文件（测试独占）
- 工作报告（按阶段命名，不冲突）

**实现**：无需额外保护，直接 `Path.write_text()`。

**目录约定**：
```
.ai-rd-team/runtime/artifacts/
├── design/                 # 架构师产出
├── code/                   # 开发者产出（按开发者名分子目录或文件名前缀）
├── test/                   # 测试产出
└── reports/                # 工作报告
```

### S2：原子 rename（**状态文件用**）

**适用场景**：团队全局状态、单一事实源
- `team-state.yaml`（团队整体状态）
- `current-phase.json`（当前阶段）
- 每个成员的 `status.yaml`

**实现**：
```python
def atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.replace(tmp, path)
```

**注意**：last-write-wins 策略，写入者需确认自己拥有写权限（避免并发冲突）。

### S3：fcntl 文件锁（**追加日志用**）

**适用场景**：多成员共享的追加日志
- `team-messages.log`（消息流水）
- `events.jsonl`（事件日志）
- 统一的行为日志

**实现**：
```python
with path.open("a") as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        f.write(record)
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

**注意**：
- Windows 没有 fcntl，需降级到 `portalocker` 或应用层锁
- ai-rd-team 第一期建议 Linux/Mac 优先，Windows 列为兼容目标

## 给详细设计 `07-artifacts.md` 的输入

1. **制品目录结构**：按"成员类型 + 阶段"分目录，避免同名文件冲突
2. **文件命名规范**：使用"阶段前缀"+"角色前缀"+"内容主题"形式
   - 例：`design-architecture.md`、`code-user-service.go`、`test-auth.py`
3. **三种写入策略明确定位**：默认 S1，状态用 S2，日志用 S3
4. **跨平台兼容**：fcntl 在 Windows 不可用，需加抽象层 + 降级方案
5. **并发读写**：多成员同时读同一文件（如 design-note.md）无需保护，直接读

## 原型验证的 P4 项 - 结论

**✅ 成立**：Python 多线程环境下，制品并发写是可控的。

**需要在正式实现中补充的**：
- 跨平台文件锁抽象（优先 fcntl，Windows 降级）
- 冲突可检测（文件 SHA 对比）
- 写入失败的重试与告警
