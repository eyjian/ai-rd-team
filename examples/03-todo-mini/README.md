# 示例 03：TodoMini（微信小程序 TodoList）

**档位**：Standard  
**技术栈**：微信小程序（原生）+ 云开发（可选）  
**预计 RP**：300-400  
**预计时长**：15-25 分钟  

## 目标产出

一个 TodoList 微信小程序，支持：

- 列表页：显示所有待办（按完成状态分组）
- 新建页：添加任务（标题、优先级、截止日期）
- 详情页：查看、编辑、删除
- tabBar：待办 / 已完成 / 我的

## 团队配置

Standard 档默认（architect + developer × 2 + tester）
- architect 决定页面结构 / 组件拆分 / 数据流
- developer_1 实现页面（wxml + wxss + 业务 js）
- developer_2 实现通用组件 + 本地存储服务
- tester 写业务逻辑单测（store 层）

## 预期文件树

```
.ai-rd-team/runtime/artifacts/code/
├── miniprogram/
│   ├── app.js / app.json / app.wxss
│   ├── project.config.json
│   ├── pages/
│   │   ├── todo-list/
│   │   │   ├── index.js / index.json
│   │   │   ├── index.wxml / index.wxss
│   │   ├── todo-detail/
│   │   ├── todo-new/
│   │   └── me/
│   ├── components/
│   │   ├── todo-item/                  # 可复用单项
│   │   └── priority-badge/
│   ├── services/
│   │   └── todo-store.js               # 本地存储封装
│   └── utils/
│       └── date.js
└── tests/                              # Node 环境 Jest 测 services/
    └── todo-store.test.js
```

## 如何运行

```bash
cp -r examples/03-todo-mini ~/demo-todo-mini
cd ~/demo-todo-mini

ai-rd-team serve --port 8765 &
ai-rd-team run "$(cat REQUIREMENT.md)"
```

成员产出后：

1. 下载微信开发者工具
2. 导入 `.ai-rd-team/runtime/artifacts/code/` 作为项目目录
3. 预览效果

## 验收标准

1. 微信开发者工具能打开项目不报错
2. 4 个页面 + 2 个组件完整
3. `services/todo-store.js` 有对应 Jest 测试且全过
4. tabBar 切换流畅（无样式错位）
