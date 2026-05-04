做一个微信小程序叫 TodoMini，用原生框架（不用 uni-app / Taro）。

## 页面

### 1. 待办列表（tabBar 第 1 页，pages/todo-list/）
- 按「未完成」「已完成」两组展示
- 每项显示：标题、优先级徽章、截止日期、勾选框
- 点击勾选 → 切换 done 状态
- 右上角「+」按钮 → 跳转新建页

### 2. 新建（pages/todo-new/）
- 表单：标题（必填）、优先级（低/中/高）、截止日期（可选，date picker）
- 保存按钮：写入 store，返回列表页

### 3. 详情（pages/todo-detail/）
- 路由参数传 id
- 展示所有字段 + 编辑 + 删除按钮
- 编辑模式：可改标题 / 优先级 / 截止日期 / done
- 删除：showModal 确认后删

### 4. 我的（tabBar 第 2 页，pages/me/）
- 显示统计：总数、已完成数、完成率
- 一个「清空已完成」按钮

## 组件

### todo-item
- 可复用的单项显示组件，接收 todo 对象作为 prop
- 支持 toggle 事件（勾选 / 取消）和 tap 事件（跳详情）

### priority-badge
- 根据 priority 属性（low/medium/high）显示不同颜色小徽章

## 数据

- 存在 `wx.setStorageSync('todos', [...])` 里
- Todo 模型：
  ```javascript
  {
    id: "ulid",         // 或时间戳字符串
    title: "...",
    priority: "medium",  // low / medium / high
    dueDate: null,       // ISO 8601 或 null
    done: false,
    createdAt: "ISO 8601"
  }
  ```

## 技术要求

- 原生微信小程序（无 uni-app / Taro）
- 所有 wx.* API 用 Promise 封装（utils/wx-promise.js）
- 业务逻辑抽到 services/todo-store.js（纯 JS，方便 Node + Jest 测试）
- 样式全用 rpx，不用 px
- tabBar 用小程序官方 tabBar（app.json 配置）

## 非目标

- 不做云同步（纯本地 Storage）
- 不做分享到朋友圈
- 不做订阅消息提醒
- 不做用户登录
