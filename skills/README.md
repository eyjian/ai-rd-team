# ⚠️ 此目录已迁移（0.1.0b1 → M6 修复）

此目录**已不再**存放 CodeBuddy Skill 文件。

## 新位置

ai-rd-team 的 CodeBuddy Skills 已重组为标准 **CodeBuddy marketplace 结构**，位于：

```
<repo-root>/
├── .codebuddy-plugin/
│   └── marketplace.json               ← marketplace 声明
└── plugins/
    └── ai-rd-team/
        ├── .codebuddy-plugin/
        │   └── plugin.json            ← plugin 元数据
        └── skills/
            ├── ai-rd-team-launcher/
            │   └── SKILL.md
            └── ai-rd-team-bridge/
                └── SKILL.md
```

## 为什么迁移

原结构是**单 `.md` 文件 + YAML frontmatter**，放在 `<repo>/skills/` 下，让用户 `ln -s ~/.codebuddy/plugins/marketplaces/local/skills/`。

这个设计从 M1 就是错的——**CodeBuddy 根本不扫描 `marketplaces/local/skills/` 这种路径**。`marketplaces/<name>/plugins/<plugin>/skills/<skill>/SKILL.md` 才是官方约定的四层结构。

M6 修复把项目结构改成与 `codebuddy-plugins-official` / `obra_superpowers-marketplace` 完全一致，可以直接被 CodeBuddy 识别。

## 怎么用新结构安装

```bash
ai-rd-team skills   # 工具会告诉你 marketplace 根路径 + 安装命令
```

**推荐命令**（已真机验证）：

```bash
codebuddy plugin marketplace add /path/to/ai-rd-team
codebuddy plugin install ai-rd-team@ai-rd-team
# 然后重启 CodeBuddy IDE
```

详见：
- [docs/01-getting-started.md § 第 2 步](../docs/01-getting-started.md#第-2-步把-skill-安装到-codebuddy只做一次)
- [README.md § 方式 C](../README.md)

## 相关提交

- 旧单文件 Skill → 新 plugin+SKILL.md 目录式：见 git log 搜 `M6 fix: codebuddy marketplace 规范化`
