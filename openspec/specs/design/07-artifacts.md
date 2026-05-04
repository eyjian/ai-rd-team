# ai-rd-team 详细设计 - 07 制品体系

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：中等详细
> 依赖：`00-overview.md`、`01-engine.md`、`05-roles-skills.md`
> 来自原型：P4（三种并发写策略已验证）

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 中**制品（Artifact）的格式、命名、目录结构、并发写策略**。制品是团队工作的最终可交付物，也是断点续跑、Web 展示、审计追溯的依据。

### 1.2 范围
- 制品命名规范（5 类前缀）
- 目录结构（artifacts/ 下按角色分层）
- 文件格式标准（Markdown / YAML / JSON / 代码）
- 三种并发写策略（基于 P4 验证）
- ArtifactRecorder 工具类接口
- 制品 Schema 约定（关键类型）

### 1.3 非目标
- ❌ 具体业务文档（PRD / 架构方案）的详细模板（属于各角色的 Skills 职责）
- ❌ 运行时状态文件格式（见 `11-runtime-protocol.md`）

---

## 2. 核心原则

### 2.1 产物即汇报

成员不通过"给 main 发长消息"汇报工作，而是**写文件**。文件存在就是工作完成的证据。Web 面板通过文件监听感知进度。

### 2.2 命名即分类

文件名前缀直接体现类型。一眼看出是"规范文档"还是"数据文件"还是"执行结果"。

### 2.3 所有制品可追溯来源

通过文件名的 `{owner}` 前缀 + 时间戳 + 目录结构，任何制品都能定位到：谁在什么时候产出的、属于哪个阶段、与哪些其他文件相关。

### 2.4 并发写靠约定而非锁

多数情况下，让不同成员写不同文件（P4 的 S1 策略）。只有少数场景（共享状态、日志）才用锁。

---

## 3. 制品命名规范

### 3.1 五类前缀

基于头脑风暴确定的命名约定：

| 前缀 | 类型 | 内容 | 典型文件 |
|------|------|------|---------|
| `spec-` | 规范文档 | 人类阅读为主的说明性文档（含图表） | `spec-requirements.md` / `spec-architecture.md` |
| `data-` | 结构化数据 | YAML / JSON 机器解析 | `data-interfaces.yaml` / `data-bugs.yaml` |
| `result-` | 执行结果 | 某次操作的产出记录 | `result-test-run-20260504.md` |
| `log-` | 过程记录 | 时间序列日志 | `log-review-rounds.jsonl` |
| `report-` | 工作报告 | 成员 / 阶段总结 | `report-architect.md` / `report-phase-dev.md` |

**代码文件**不加前缀（按语言惯例命名，如 `user_service.go`、`UserProfile.vue`）。

### 3.2 完整命名模板

```
[owner-]{prefix}-{topic}[-{extra}].{ext}
```

| 位 | 必填 | 说明 |
|----|-----|------|
| `owner-` | 可选 | 多人同类型产出时加 owner 前缀（如 `developer_1-user-api.go`） |
| `{prefix}` | 是 | 五类前缀之一（代码文件除外） |
| `{topic}` | 是 | 主题（kebab-case），如 `architecture`、`user-module` |
| `{extra}` | 可选 | 如版本号、时间戳、轮次 |
| `.{ext}` | 是 | 扩展名 |

**示例**：
- `spec-architecture.md`（单人产出）
- `developer_1-user-service.go`（多人产出用 owner 前缀）
- `result-test-run-20260504-143022.md`（带时间戳）
- `spec-review-user-module-round2.md`（带轮次）

### 3.3 owner 前缀规则

| 场景 | 是否用 owner |
|------|------------|
| 单角色独占产出（如 architect 的 `spec-architecture.md`） | ❌ 不用 |
| 多实例同角色产出相同类型（如 2 个 developer） | ✅ 用 `developer_1-` / `developer_2-` |
| 跨角色共享文件（罕见） | ❌ 不用 owner，改用共享目录 `shared/` |

---

## 4. 目录结构

### 4.1 artifacts/ 完整结构

基于原型 P1 验证 + 头脑风暴约定：

```
<workspace>/.ai-rd-team/runtime/artifacts/
├── requirements/               # 需求分析（analyst 产出）
│   ├── spec-requirements.md
│   ├── data-requirements.yaml
│   └── spec-business-context.md
│
├── design/                     # 架构设计（architect 产出）
│   ├── spec-architecture.md
│   ├── spec-architecture-diagrams.md   # 或合并到主文档
│   ├── data-interfaces.yaml            # API 契约
│   ├── data-schemas.yaml               # DB / Redis / 协议定义
│   ├── data-task-breakdown.yaml        # 任务拆分（给 developers 看）
│   └── adr/                            # 决策记录（链接到 memory/decisions）
│       └── README.md                   # 说明：真实 ADR 在 memory/decisions/
│
├── code/                       # 代码产出（developer 产出）
│   ├── {developer_1-}user-service.go
│   ├── {developer_2-}order-api.go
│   ├── frontend/
│   │   ├── UserProfile.vue
│   │   └── ...
│   └── miniprogram/
│       └── ...
│
├── review/                     # 评审（reviewer 产出）
│   ├── spec-review-user-module.md
│   ├── data-review-issues-user-module.yaml
│   └── log-review-rounds.jsonl         # 评审过程记录
│
├── test/                       # 测试（tester 产出）
│   ├── spec-test-plan.md
│   ├── test_user_service.py            # 测试代码
│   ├── test_order_api.py
│   ├── result-test-run-{timestamp}.md  # 每次执行结果
│   └── data-bugs.yaml                  # Bug 清单
│
├── deployment/                 # 部署（devops 产出）
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── deploy/
│   │   ├── k8s-user-service.yaml
│   │   └── ...
│   ├── .github/workflows/ci.yaml       # （实际写到项目根目录的引用副本）
│   └── report-deployment.md
│
├── reports/                    # 工作报告（pm + 各角色）
│   ├── report-architect.md             # 架构师总结
│   ├── report-phase-requirements.md    # 需求阶段总结
│   ├── report-phase-dev.md             # 开发阶段总结
│   ├── report-phase-review.md
│   ├── report-phase-test.md
│   └── report-run-summary.md           # 本次运行总览（pm 或 engine 写）
│
└── delivery/                   # 交付清单（最终产物索引）
    ├── spec-delivery-checklist.md
    └── data-delivery-manifest.yaml
```

### 4.2 目录 ↔ 角色映射

```python
ROLE_TO_DIR = {
    "pm": "reports",
    "analyst": "requirements",
    "architect": "design",
    "developer": "code",
    "reviewer": "review",
    "tester": "test",
    "devops": "deployment",
}
```

**两个例外**：
- **reports/** 是 **PM 主目录 + 各角色都写阶段报告**（不独占）
- **delivery/** 由 PM 或 engine 在项目结束时统一产出

### 4.3 代码产物的落位选择

代码文件有两种落位策略：

**策略 A：落到 `artifacts/code/`（原型阶段）**
- 优点：便于回溯、不污染项目源目录
- 缺点：不是最终产品位置，需要用户手动拷贝

**策略 B：落到项目真实源码目录（如 `src/`, `pkg/`）**（推荐第一期默认）
- 优点：跑起来就是真实项目
- 缺点：可能覆盖已有文件

**配置决定**：

```yaml
# config.advanced.yaml
artifacts:
  code_output:
    strategy: "in_place"            # in_place / artifacts_only / both
    # in_place: 写到项目真实目录（推荐）
    # artifacts_only: 只写 artifacts/code/（用于评估阶段）
    # both: 两处都写（artifacts/code/ 作为快照）
    project_root_writable: true     # 是否允许写项目根目录（默认 true，由 security 覆盖）
```

**safety 约束**：无论哪种策略，都必须遵守 `security.file_access.writable` 约束。

---

## 5. 文件格式标准

### 5.1 Markdown 文件（spec- / report-）

#### 通用结构

```markdown
# {标题}

> 作者：{成员 display_name}（{role}）
> 日期：2026-05-04
> 状态：draft / reviewed / final
> 版本：v1.0
> 相关：[link to 其他制品]

---

## 1. 背景 / 目的

## 2. 核心内容

## 3. ...

## 附录（可选）
- 引用
- 术语表
```

**必填头信息**：作者 / 日期 / 状态。便于 Web 面板列表展示。

#### 分类要求

| 文件 | 必含章节 |
|------|---------|
| `spec-requirements.md` | 业务背景、名词解释、业务流程图（mermaid）、功能清单、非功能需求、边界 |
| `spec-architecture.md` | 技术方案、技术栈选择、类图、时序图、数据流、部署拓扑、关键决策 |
| `spec-test-plan.md` | 测试策略、覆盖范围、用例矩阵、环境约束、风险 |
| `spec-review-*.md` | 评审范围、发现 issues、建议、结论 |
| `report-*.md` | 工作摘要、已完成、进行中、阻塞、资源消耗 |

### 5.2 YAML 文件（data-）

用于机器解析，必须符合**明确的 Schema**。

#### 核心 data 文件 Schema

**`data-requirements.yaml`**：

```yaml
version: "1.0"
project:
  name: string
  description: string
requirements:
  - id: "REQ-001"
    title: "用户注册"
    category: "functional"           # functional / non_functional / constraint
    priority: "P0"                   # P0/P1/P2
    description: |
      用户能通过邮箱或手机号注册...
    acceptance_criteria:
      - "输入合法邮箱能收到验证邮件"
      - "密码需满足 8 位以上复杂度要求"
    depends_on: []                   # 依赖的其他 REQ-ID
  - ...
```

**`data-interfaces.yaml`**：

```yaml
version: "1.0"
apis:
  - id: "API-USER-001"
    method: "POST"
    path: "/api/users/register"
    summary: "用户注册"
    request:
      body:
        type: "object"
        required: ["email", "password"]
        properties:
          email: {type: "string", format: "email"}
          password: {type: "string", minLength: 8}
    responses:
      200:
        body: {user_id: "string", token: "string"}
      400: {error: "string"}
    owner: "developer_1"              # 谁负责实现
  - ...

# 数据模型（若项目有数据库）
schemas:
  - name: "User"
    type: "sql"                       # sql / nosql / redis
    table: "users"
    fields:
      - {name: "id", type: "bigint", pk: true, auto: true}
      - {name: "email", type: "varchar(255)", unique: true, not_null: true}
      - {name: "password_hash", type: "varchar(255)", not_null: true}
      - {name: "created_at", type: "timestamp", default: "CURRENT_TIMESTAMP"}
    indexes:
      - {name: "idx_email", columns: ["email"]}

# Redis key 约定（若用）
redis_keys:
  - pattern: "user:session:{user_id}"
    type: "hash"
    ttl_seconds: 7200
    fields: {user_id: "bigint", ip: "string"}
```

**`data-task-breakdown.yaml`**：

```yaml
version: "1.0"
breakdown_by: "architect"
tasks:
  - id: "T001"
    title: "实现用户注册 API"
    assignee: "developer_1"
    depends_on: []
    estimated_points: 20
    files_to_create:
      - "src/api/user_register.go"
      - "src/api/user_register_test.go"
    interfaces_to_implement: ["API-USER-001"]
    acceptance:
      - "通过 API-USER-001 的契约测试"
      - "代码评审通过"
      - "单测覆盖 ≥ 80%"
  - ...
parallel_groups:
  - group_id: "auth"
    tasks: ["T001", "T002"]          # 这组可并行
  - group_id: "profile"
    tasks: ["T003"]
    depends_on_groups: ["auth"]      # 等 auth 完成
```

**`data-review-issues-{module}.yaml`**：

```yaml
version: "1.0"
reviewer: "reviewer"                 # 或 "王1号"
reviewed_files:
  - "src/api/user_register.go"
round: 1                             # 第几轮评审
issues:
  - id: "ISS-001"
    severity: "blocker"              # blocker / major / minor / nit
    category: "security"             # security / correctness / readability / performance / style
    file: "src/api/user_register.go"
    line: 42
    description: "密码未做 bcrypt 哈希，直接明文存储"
    suggestion: "使用 bcrypt.GenerateFromPassword(password, bcrypt.DefaultCost)"
    status: "open"                   # open / fixed / wontfix / discussing
  - ...
summary:
  total: 8
  blocker: 1
  major: 2
  minor: 5
  nit: 0
verdict: "blocked"                   # approved / approved_with_changes / blocked
```

**`data-bugs.yaml`**：

```yaml
version: "1.0"
reporter: "tester"
bugs:
  - id: "BUG-001"
    severity: "critical"             # critical / high / medium / low
    status: "open"                   # open / fixed / verified / wontfix
    title: "注册时 email 大小写不敏感但 DB 存的是原始大小写"
    steps_to_reproduce:
      - "用 foo@a.com 注册"
      - "再用 FOO@a.com 注册（期望拒绝，实际成功）"
    expected: "第二次注册返回 email 已存在"
    actual: "第二次注册成功，产生两个账号"
    environment:
      os: "linux"
      backend_version: "dev-a1b2c3d"
    related_api: "API-USER-001"
    assigned_to: "developer_1"
```

**`data-delivery-manifest.yaml`**：

```yaml
version: "1.0"
run_id: "xxxxxx"
completed_at: "2026-05-04T18:00:00Z"
deliverables:
  documents:
    - path: "artifacts/requirements/spec-requirements.md"
      producer: "analyst"
    - path: "artifacts/design/spec-architecture.md"
      producer: "architect"
    - ...
  code:
    - path: "src/api/user_register.go"
      producer: "developer_1"
      lines: 120
      related_tests: ["test_user_register.py"]
    - ...
  tests:
    - path: "test_user_register.py"
      producer: "tester"
      test_count: 12
      pass_count: 12
  deployment:
    - path: "Dockerfile"
      producer: "devops"
    - path: "deploy/k8s-user-service.yaml"
      producer: "devops"
  reports:
    - path: "artifacts/reports/report-run-summary.md"
      producer: "pm"

quality_metrics:
  test_pass_rate: 1.0
  review_blockers_open: 0
  code_coverage: 0.85
  total_resource_points: 385

how_to_run:
  - "按 Dockerfile 构建镜像：docker build -t my-app ."
  - "启动服务：docker-compose up"
  - "验证：curl http://localhost:8080/health"
```

### 5.3 JSON / JSONL 文件（log-）

用于**追加式日志**。每行一个对象。

**`log-review-rounds.jsonl`**：

```jsonl
{"ts":"2026-05-04T14:00:00Z","round":1,"reviewer":"reviewer","file":"user.go","issues_count":5}
{"ts":"2026-05-04T14:30:00Z","round":1,"event":"fixed","issue_id":"ISS-001","fixer":"developer_1"}
{"ts":"2026-05-04T15:00:00Z","round":2,"reviewer":"reviewer","file":"user.go","issues_count":1}
```

### 5.4 代码文件

无前缀，按语言惯例命名。  
**成员必须**：
- 文件顶部加 docstring / 注释，说明：
  - 产出者（`@author` 或项目约定）
  - 关联的接口 / 需求 ID（如 `# Implements: API-USER-001`）
- 配套测试文件（tester 产出，可能在独立目录）

---

## 6. 并发写策略（基于 P4 验证）

### 6.1 三种策略分工

| 策略 | 适用场景 | 实现 |
|------|---------|------|
| **S1：不同文件并发写**（默认） | 各成员写各自文件（`spec-*`、代码、测试、报告） | `Path.write_text()` 直接 |
| **S2：原子 rename** | 状态文件（`team.yaml`、`members/*.yaml`、`current-run.yaml`） | 先写 `.tmp` → `os.replace()` |
| **S3：fcntl 文件锁** | 追加日志（`log-*.jsonl`、`events.jsonl`） | `fcntl.flock(LOCK_EX)` 后 append |

### 6.2 file_ops 工具模块

```python
# ai_rd_team/shared/file_ops.py

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path


# S2：原子写
def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """原子写：先写临时文件，再 rename。
    
    适用：状态文件（last-write-wins，保证读到的永远是完整内容）
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# S3：带锁追加
def locked_append(path: Path, content: str, encoding: str = "utf-8") -> None:
    """带锁追加：多进程/线程共享日志文件。
    
    Linux/Mac 用 fcntl；Windows 降级到 portalocker 或应用层锁。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        _append_windows(path, content, encoding)
    else:
        _append_fcntl(path, content, encoding)


def _append_fcntl(path: Path, content: str, encoding: str) -> None:
    import fcntl
    with open(path, "a", encoding=encoding) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _append_windows(path: Path, content: str, encoding: str) -> None:
    """Windows 降级：优先用 portalocker，没安装则用进程内 threading.Lock。"""
    try:
        import portalocker
        with open(path, "a", encoding=encoding) as f:
            portalocker.lock(f, portalocker.LockFlags.EXCLUSIVE)
            try:
                f.write(content)
                f.flush()
            finally:
                portalocker.unlock(f)
    except ImportError:
        import threading
        global _windows_fallback_lock
        try:
            _windows_fallback_lock
        except NameError:
            _windows_fallback_lock = threading.Lock()
        with _windows_fallback_lock:
            with open(path, "a", encoding=encoding) as f:
                f.write(content)
                f.flush()


# S1：常规写（为一致性也提供方法）
def safe_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """常规写（用于不同文件不冲突的场景）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


# 读（可能与写冲突时用）
def safe_read_yaml(path: Path) -> dict | None:
    """读 YAML，允许文件不存在。"""
    if not path.exists():
        return None
    import yaml
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text)
```

### 6.3 选用决策表

| 要写的文件 | 策略 | 理由 |
|----------|------|------|
| `spec-*.md` / `report-*.md` / 代码文件 | S1 | 单 owner 独占写，无竞争 |
| `data-*.yaml`（由单角色多轮更新） | S1 + 备份 | 同 owner 顺序更新，前版备份到 `.bak` |
| `state/team.yaml` / `state/members/{name}.yaml` | S2 原子 rename | 引擎和成员可能都更新 |
| `current-run.yaml` | S2 | 引擎独占更新，但需防断电半写 |
| `events.jsonl` / `log-*.jsonl` | S3 锁 | 多成员追加 |
| `adapter-calls.jsonl` | S3 | 同上 |

---

## 7. ArtifactRecorder 接口

### 7.1 职责

为成员提供**便利的制品写入 API**，并在写入时：
- 强制走 `security.file_access.writable` 校验
- 自动选择 S1/S2/S3 策略
- 记录到 `data-delivery-manifest.yaml`
- 触发 Hook（`artifact_written`）

### 7.2 接口

```python
# ai_rd_team/artifacts/recorder.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class ArtifactCategory(str, Enum):
    SPEC = "spec"          # spec-*.md
    DATA = "data"          # data-*.yaml
    RESULT = "result"      # result-*.md
    LOG = "log"            # log-*.jsonl
    REPORT = "report"      # report-*.md
    CODE = "code"          # 代码文件
    BINARY = "binary"      # 二进制（图片等）


@dataclass(frozen=True)
class ArtifactRecord:
    producer: str              # 成员 instance_name
    category: ArtifactCategory
    path: Path                 # 相对 artifacts/ 或绝对路径
    size_bytes: int
    estimated_tokens: int
    written_at: datetime
    sha1: str                  # 内容哈希


class ArtifactRecorder:
    """制品写入器。
    
    成员通过此类写文件，获得：
    - security 检查
    - 自动选择并发策略
    - 自动登记到 manifest
    - 自动触发 Hook
    """
    
    def __init__(
        self,
        runtime_dir: Path,
        producer: str,
        security_rules: "SecurityRules",
        hook_runner: "HookRunner" | None = None,
    ):
        self.runtime_dir = runtime_dir
        self.producer = producer
        self.security = security_rules
        self.hook_runner = hook_runner
    
    def write(
        self,
        relative_path: str,            # 相对 artifacts/ 根
        content: str,
        category: ArtifactCategory | None = None,
    ) -> ArtifactRecord:
        """写一个制品。
        
        1. 路径校验（security）
        2. 自动推断 category（若未指定）
        3. 根据 category 选策略（S1/S2/S3）
        4. 写文件
        5. 登记到 manifest
        6. 触发 Hook
        """
        full_path = (self.runtime_dir / "artifacts" / relative_path).resolve()
        self._check_writable(full_path)
        
        cat = category or self._infer_category(relative_path)
        strategy = self._choose_strategy(cat)
        
        if strategy == "atomic":
            from ai_rd_team.shared.file_ops import atomic_write
            atomic_write(full_path, content)
        elif strategy == "locked_append":
            from ai_rd_team.shared.file_ops import locked_append
            locked_append(full_path, content)
        else:  # safe_write
            from ai_rd_team.shared.file_ops import safe_write
            safe_write(full_path, content)
        
        record = self._make_record(
            producer=self.producer,
            category=cat,
            path=full_path,
            content=content,
        )
        self._register_manifest(record)
        if self.hook_runner:
            self.hook_runner.trigger(
                "artifact_written",
                producer=self.producer,
                path=str(full_path),
                category=cat.value,
            )
        return record
    
    def write_code(
        self,
        relative_path: str,            # 相对项目根（如 "src/api/user.go"）
        content: str,
    ) -> ArtifactRecord:
        """写代码到项目根（受 artifacts.code_output.strategy 控制）。"""
    
    def append_log(
        self,
        relative_path: str,
        line: str,
    ) -> None:
        """便捷方法：追加一行到 log-*.jsonl。"""
    
    # ===== 辅助 =====
    
    def _check_writable(self, path: Path) -> None:
        """security 校验。"""
    
    def _infer_category(self, relative_path: str) -> ArtifactCategory:
        """从文件名前缀推断类型。"""
        name = Path(relative_path).name.lower()
        for prefix in ("spec-", "data-", "result-", "log-", "report-"):
            if name.startswith(prefix):
                return ArtifactCategory(prefix.rstrip("-"))
        if name.endswith((".py", ".go", ".js", ".ts", ".vue", ".java", ".rs", ".cpp")):
            return ArtifactCategory.CODE
        return ArtifactCategory.BINARY
    
    def _choose_strategy(self, cat: ArtifactCategory) -> str:
        if cat == ArtifactCategory.LOG:
            return "locked_append"
        return "safe_write"  # 默认
        # 注：S2 atomic_write 由 RuntimeStateManager 而非 Recorder 调用
    
    def _make_record(self, **kwargs) -> ArtifactRecord: ...
    
    def _register_manifest(self, record: ArtifactRecord) -> None:
        """登记到 artifacts/delivery/data-delivery-manifest.yaml。"""
```

### 7.3 成员如何调用

在 CodeBuddy 环境下，成员**不直接调用 Python API**（成员是 sub-agent 写 prompt 的），而是：

1. **成员通过 Write 工具直接写文件** — 引擎旁路监听 `artifacts/` 变化
2. **FileWatcher 发现新文件** → 自动触发 ArtifactRecorder 的 `_register_manifest` 和 hook

**但**：`state/members/*.yaml` 的更新应由成员**主动写**（因为这是自报状态的证据），引擎不干预。

这种"**成员写文件 + 引擎观察文件**"的模式与 P1/P3/P4 的验证完全一致。

---

## 8. 版本管理与备份

### 8.1 同 owner 多轮更新

像 `data-bugs.yaml` 这种 tester 可能多次更新的文件：

```
artifacts/test/
├── data-bugs.yaml                    # 最新版
├── data-bugs.yaml.v1.bak             # 第一版（首次写入时不备份）
├── data-bugs.yaml.v2.bak             # 第二版
└── data-bugs.yaml.v3.bak
```

**规则**：
- 第一次写不备份
- 后续每次写：先把当前版本 copy 为 `{name}.v{N}.bak`，再写新版本
- N 从 1 开始递增
- 最多保留 5 版（更老的自动清理）

**实现**：由 ArtifactRecorder 自动处理（不让成员管）。

### 8.2 跨 run 归档

每次运行结束，`runtime/` 整体归档到 `archive/run-{uuid}/`（由 `01-engine.md §6.3` 的 `archive_team` 完成）。制品随之归档。

---

## 9. 制品的索引与查询

### 9.1 manifest 文件

`artifacts/delivery/data-delivery-manifest.yaml` 维护**本次运行所有制品的索引**。由引擎/PM 在运行结束时生成；ArtifactRecorder 在每次写入时增量更新。

### 9.2 Web 面板查询路径

Web 面板通过以下方式展示制品：

1. 列出 `artifacts/*/` 所有文件 → 列表
2. 读 `data-delivery-manifest.yaml` → 元信息（产出者/类型/时间）
3. 读每个文件的 Markdown 头部（§5.1）→ 状态/版本
4. 点击后读取全文 → 在线预览

---

## 10. 典型制品流（以 Standard 档为例）

### 10.1 时序

```
T0: architect 写 artifacts/design/spec-architecture.md
T0+: architect 写 artifacts/design/data-interfaces.yaml
T1: developer_1 读 data-interfaces.yaml → 写 src/api/user.go
    （同时写快照 artifacts/code/developer_1-user.go，若 strategy=both）
T1+: developer_2 读 data-interfaces.yaml → 写 src/api/order.go
T2: reviewer 读 developer_1/2 的代码 → 写 artifacts/review/spec-review-user-module.md
    + data-review-issues-user-module.yaml
T3: developer_1 修改 src/api/user.go（按 review issues）
T4: tester 写 test_user.py 并执行 → 写 result-test-run-{ts}.md
T5: 完成，pm 写 report-run-summary.md + data-delivery-manifest.yaml
```

### 10.2 并发写验证

- T0 / T0+：architect 顺序写两个不同文件 — 无冲突（S1）
- T1 / T1+：developer_1 和 developer_2 并发写不同文件 — 无冲突（S1）
- T2：reviewer 写新文件 — 无冲突
- 整个过程中 `events.jsonl` 被多方追加 — 用 fcntl 锁（S3）
- 引擎维护 `current-run.yaml` 更新 — 用原子 rename（S2）

**P4 已证实这套策略在多线程并发下无数据损坏。**

---

## 11. 验收标准

- ✅ 五类前缀命名约定贯穿所有成员 Skills 中
- ✅ artifacts/ 目录结构按 §4.1 创建
- ✅ 所有"data-*.yaml" 符合 §5.2 的 Schema（可用 JSON Schema 校验）
- ✅ file_ops 工具提供 S1/S2/S3 三个方法，Linux/Mac/Windows 三平台均可用
- ✅ ArtifactRecorder 能自动推断类型并选对策略
- ✅ 代码文件的 in_place / artifacts_only / both 三种策略可配置
- ✅ manifest 文件能被 ArtifactRecorder 增量更新
- ✅ 同 owner 多轮写 data-*.yaml 时自动备份 .v{N}.bak
- ✅ FileWatcher 能感知 artifacts/ 变化并触发 Hook
- ✅ 单元测试覆盖 ≥ 80%（三种并发策略 + 各文件格式校验）

---

## 12. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | runtime/artifacts 目录结构；ArtifactRecorder 初始化 |
| `05-roles-skills.md` | 各角色的 `产出主文件前缀` 依照本文档定义 |
| `09-hooks-security.md` | `artifact_written` Hook；`security.file_access` 校验 |
| `04-web-panel.md` | 通过 manifest 展示制品列表 + Markdown 在线预览 |
| `11-runtime-protocol.md` | `state/` 目录用 S2 原子写；`events.jsonl` 用 S3 锁追加 |
| `08-cost-control.md` | manifest 中记录每个制品的 `estimated_tokens` 供成本分析 |
| `06-memory-system.md` | ADR 制品落在 `memory/decisions/` 而非 `artifacts/design/adr/`（后者只放引用） |

---

## 13. 附录：制品命名速查表

| 想写什么 | 用什么文件名 | 放哪 | 策略 |
|---------|-----------|------|------|
| 需求分析文档 | `spec-requirements.md` | `requirements/` | S1 |
| 需求条目（结构化） | `data-requirements.yaml` | `requirements/` | S1 |
| 架构方案 | `spec-architecture.md` | `design/` | S1 |
| 接口契约 | `data-interfaces.yaml` | `design/` | S1 |
| 数据模型 | `data-schemas.yaml` | `design/` | S1 |
| 任务拆分 | `data-task-breakdown.yaml` | `design/` | S1 |
| 代码（默认项目源目录） | `{module}.{ext}` | `src/`、`web/` 等 | S1 |
| 代码快照（若启用） | `developer_1-{module}.{ext}` | `code/` | S1 |
| 评审报告 | `spec-review-{module}.md` | `review/` | S1 |
| 评审 issues | `data-review-issues-{module}.yaml` | `review/` | S1 |
| 评审过程日志 | `log-review-rounds.jsonl` | `review/` | S3 |
| 测试计划 | `spec-test-plan.md` | `test/` | S1 |
| 测试代码 | `test_{module}.{ext}` | `test/` | S1 |
| 测试执行结果 | `result-test-run-{ts}.md` | `test/` | S1 |
| Bug 列表 | `data-bugs.yaml` | `test/` | S1 + 版本备份 |
| Dockerfile / CI | 按惯例 | `deployment/` or 项目根 | S1 |
| 部署报告 | `report-deployment.md` | `deployment/` | S1 |
| 工作报告（角色） | `report-{role}.md` | `reports/` | S1 |
| 阶段报告 | `report-phase-{name}.md` | `reports/` | S1 |
| 运行总结 | `report-run-summary.md` | `reports/` | S1 |
| 交付清单 | `spec-delivery-checklist.md` | `delivery/` | S1 |
| 交付索引 | `data-delivery-manifest.yaml` | `delivery/` | S1（ArtifactRecorder 增量更新） |
