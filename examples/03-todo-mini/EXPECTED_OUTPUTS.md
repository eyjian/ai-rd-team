# TodoMini 预期产出

## 文件树

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── miniprogram/
│   │   ├── app.js / app.json / app.wxss
│   │   ├── project.config.json
│   │   ├── pages/
│   │   │   ├── todo-list/index.{js,json,wxml,wxss}
│   │   │   ├── todo-new/index.{js,json,wxml,wxss}
│   │   │   ├── todo-detail/index.{js,json,wxml,wxss}
│   │   │   └── me/index.{js,json,wxml,wxss}
│   │   ├── components/
│   │   │   ├── todo-item/index.{js,json,wxml,wxss}
│   │   │   └── priority-badge/index.{js,json,wxml,wxss}
│   │   ├── services/todo-store.js
│   │   └── utils/{wx-promise.js, date.js}
│   ├── tests/
│   │   ├── todo-store.test.js
│   │   └── package.json                # 只含 devDependencies (jest)
│   └── README.md                       # 用法说明
└── reports/
    ├── report-architect.md
    ├── report-developer.md
    └── report-tester.md
```

## 验收

1. 微信开发者工具打开 `.ai-rd-team/runtime/artifacts/code/miniprogram/`，能正常编译不报错
2. 4 个页面能切换、交互正常：
   - 新建 → 列表显示新条目
   - 勾选 → 移到「已完成」分组
   - 详情 → 能编辑、能删除
   - 我的 → 统计数字正确
3. tabBar 切换流畅
4. `cd .ai-rd-team/runtime/artifacts/code/tests && npm install && npx jest` 全过

## 成本预期

- RP 消耗：~280-400（Standard 档预算 400）
- 成员数：4（architect + developer × 2 + tester）
- 运行时长：15-25 分钟

## 可能遇到的问题

- **成员产出 wxml 时把 {{ }} 写成了 Vue 风格**：pytest-guide Skill 不涉及 Vue，但 wxmini-basics 已覆盖微信小程序语法
- **setData 性能警告**：成员应该避免一次 setData 整个 todos 数组（改用 index 更新）
- **Storage 键名冲突**：`wx.setStorageSync('todos', ...)` 是全局键，建议用 project 前缀（如 `todomini.todos`）
