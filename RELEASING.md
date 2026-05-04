# 发布流程

本项目用 [Hatchling](https://hatch.pypa.io/) 构建，[Twine](https://twine.readthedocs.io/) 上传。

## 0.1.0a1 → TestPyPI（当前状态）

### 前置：TestPyPI 账号与 API Token

1. 注册账号：https://test.pypi.org/account/register/
2. 账号 → API tokens → "Add API token"
   - Token name：`ai-rd-team-upload`
   - Scope：先选 "Entire account"（首发）；后续可改为单项目 scope
3. 配置 `~/.pypirc`：

```ini
[distutils]
index-servers =
    testpypi
    pypi

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-<你的 test.pypi.org token 粘贴在这里>

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-<你的 pypi.org token 粘贴在这里>
```

**安全**：`.pypirc` 含敏感 token，`chmod 600 ~/.pypirc` + 不要提交到 git。

### 构建 + 检查

```bash
# 确保在 main 分支，工作区干净
git status  # → nothing to commit, working tree clean

# 装发布工具
pip install -e ".[publish]"

# 清理旧产物
rm -rf dist/ build/ *.egg-info

# 构建（sdist + wheel）
python -m build

# Twine 验证 metadata 合法性
python -m twine check dist/*
# → dist/ai_rd_team-0.1.0a1-py3-none-any.whl: PASSED
# → dist/ai_rd_team-0.1.0a1.tar.gz: PASSED
```

### 本地干净 venv 冒烟

```bash
# 在独立 venv 装 wheel 验证
python -m venv /tmp/verify-release
source /tmp/verify-release/bin/activate
pip install dist/ai_rd_team-*.whl

# 关键命令冒烟
ai-rd-team version                   # → ai-rd-team v0.1.0a1
ai-rd-team --help                    # 列所有子命令
ai-rd-team config preset --list      # → full / lite / standard
python -c "from ai_rd_team import builtin_skills_dir; \
           import os; print(sorted(os.listdir(builtin_skills_dir())))"

deactivate
rm -rf /tmp/verify-release
```

### 上传到 TestPyPI

```bash
python -m twine upload --repository testpypi dist/*

# 输出示例：
# Uploading ai_rd_team-0.1.0a1-py3-none-any.whl
# View at: https://test.pypi.org/project/ai-rd-team/0.1.0a1/
```

### 验证 TestPyPI 可 `pip install`

```bash
python -m venv /tmp/testpypi-install
source /tmp/testpypi-install/bin/activate

# 注意：必须加 --extra-index-url 让 pip 能从 pypi.org 拉依赖
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  ai-rd-team==0.1.0a1

ai-rd-team version    # → ai-rd-team v0.1.0a1
ai-rd-team config preset --list
```

如果装得上且能跑，就成功了。

### 检查 PyPI 页面呈现

访问 https://test.pypi.org/project/ai-rd-team/0.1.0a1/，确认：

- README 渲染正常（不是纯文本或错误）
- Classifiers 显示齐全
- Project URLs 都可点击（Homepage / Docs / Changelog / Issues）
- License 显示 Apache 2.0

---

## 从 TestPyPI → PyPI 正式仓（未来）

等 TestPyPI 用户反馈稳定后再做：

1. 把 version 改成正式版（例如 `0.1.0` 或 `0.1.0b1`）
   - `pyproject.toml` 的 `version`
   - `src/ai_rd_team/__init__.py` 的 `__version__`
2. 更新 `CHANGELOG.md` 的 `[Unreleased]` → `[0.1.0]` 并加日期
3. 打 git tag：
   ```bash
   git commit -am "release: 0.1.0"
   git tag v0.1.0
   git push && git push --tags
   ```
4. 重建：
   ```bash
   rm -rf dist/ && python -m build && python -m twine check dist/*
   ```
5. 上传正式 PyPI：
   ```bash
   python -m twine upload dist/*
   ```
6. 验证：
   ```bash
   pip install ai-rd-team==0.1.0
   ai-rd-team version
   ```

---

## 版本号规范（SemVer + PEP 440）

| 阶段 | 版本 | 说明 |
|------|------|------|
| 开发中 | `0.1.0.dev1`, `0.1.0.dev2` | 不发布 |
| Alpha | `0.1.0a1`, `0.1.0a2` | TestPyPI 早期测试（当前） |
| Beta | `0.1.0b1` | 功能冻结，修 bug |
| RC | `0.1.0rc1` | 发布候选 |
| 正式 | `0.1.0` | PyPI 发布 |
| 补丁 | `0.1.1` | bugfix |
| 小版本 | `0.2.0` | 新功能，向后兼容 |
| 大版本 | `1.0.0` | 重大变更或 API 稳定 |

每次发布必须同步：
- `pyproject.toml:version`
- `src/ai_rd_team/__init__.py:__version__`
- `CHANGELOG.md` 加新版本段

---

## 发布清单（Checklist）

每次发布跑一遍：

- [ ] 在 `main` 分支，工作区干净
- [ ] 全量回归：`pytest` 全过（当前 389 测试）
- [ ] Lint：`ruff check src tests` 绿色
- [ ] Format：`ruff format --check src tests` 绿色
- [ ] 版本号同步（pyproject + `__init__.py`）
- [ ] CHANGELOG 更新（新版本段 + 日期）
- [ ] `rm -rf dist/ && python -m build`
- [ ] `python -m twine check dist/*` → PASSED
- [ ] 干净 venv 装 wheel 冒烟（version / preset / 路由）
- [ ] `twine upload`（先 TestPyPI，后 PyPI）
- [ ] 从远端 `pip install` 验证
- [ ] PyPI 页面 README / URL / classifier 呈现正确
- [ ] 打 git tag：`v<version>`
- [ ] `git push --tags`
- [ ] 在 GitHub Releases 页写 Release Notes（复制 CHANGELOG 对应段）

---

## 常见问题

### `twine upload` 报 `File already exists`

PyPI / TestPyPI **不允许重新上传同一个版本**，即使 yanked。必须 bump 版本号再传。开发期用 `0.1.0a1 → a2 → a3`。

### `pip install` 能装但运行时 `import` 失败

通常是 wheel 没打全资源（preset / skills / web HTML）。本项目已经在 `pyproject.toml` 的
`[tool.hatch.build.targets.wheel]` 显式 include 了：

```toml
include = [
    "src/ai_rd_team/**/*.py",
    "src/ai_rd_team/**/*.yaml",
    "src/ai_rd_team/**/*.md",
    "src/ai_rd_team/**/*.html",
]
```

修改打包配置后，必须重新 `rm -rf dist/ && python -m build` 验证。

### TestPyPI 上的包找不到依赖

TestPyPI 是独立 index，默认不会从 PyPI 拉依赖（fastapi / pydantic 等）。必须：

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  ai-rd-team
```
