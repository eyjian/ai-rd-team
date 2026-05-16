---
name: wxmini-basics
description: 微信小程序原生开发基础（仅微信原生，不适用 uni-app / Taro / Mpx 等跨端框架）。新建或扩展微信小程序时使用——覆盖页面四文件结构（wxml / wxss / js / json）、生命周期、`wx.*` API Promise 化、自定义组件复用、登录态与 session 管理、首屏与包大小性能优化。
default_for: []
---
# WeChat Mini Program Basics

## 适用场景

开发微信小程序（原生框架，非 uni-app / Taro）。

## 核心原则

- **页面 = 4 文件**：`.js` + `.json` + `.wxml` + `.wxss`
- **强约束生命周期**：`onLoad` / `onShow` / `onReady` / `onHide` / `onUnload`
- **wx.* API 是异步的**：用 Promise 包装，不用回调金字塔
- **状态管理**：`app.globalData`（轻）/ MobX-mini（中）/ 自写 Store（重）
- **分包加载**：超过 2MB 主包，必须分包

## 典型目录结构

```
miniprogram/
├── app.js                # 全局入口
├── app.json              # 全局配置（pages / tabBar / window）
├── app.wxss              # 全局样式
├── pages/
│   ├── index/
│   │   ├── index.js
│   │   ├── index.json
│   │   ├── index.wxml
│   │   └── index.wxss
│   └── profile/...
├── components/           # 自定义组件
├── utils/                # 工具函数
├── services/             # 业务服务封装
└── images/               # 静态资源
```

## 页面骨架

### index.wxml

```xml
<view class="container">
  <view wx:if="{{loading}}">加载中...</view>
  <view wx:else>
    <text class="title">{{title}}</text>
    <button bindtap="onRefresh">刷新</button>
    <view wx:for="{{items}}" wx:key="id" class="item">
      {{item.name}}
    </view>
  </view>
</view>
```

### index.js

```javascript
Page({
  data: {
    loading: true,
    title: '',
    items: [],
  },

  onLoad(options) {
    // options.xxx 是路由参数
    this.loadData();
  },

  onShow() {
    // 每次页面显示都会调用（含返回）
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const items = await this.fetchItems();
      this.setData({ items, title: `共 ${items.length} 条`, loading: false });
    } catch (err) {
      wx.showToast({ title: '加载失败', icon: 'error' });
      this.setData({ loading: false });
    }
  },

  fetchItems() {
    return new Promise((resolve, reject) => {
      wx.request({
        url: 'https://api.example.com/items',
        header: { Authorization: `Bearer ${wx.getStorageSync('token')}` },
        success: (res) => resolve(res.data),
        fail: reject,
      });
    });
  },

  onRefresh() {
    this.loadData();
  },
});
```

### index.json

```json
{
  "navigationBarTitleText": "首页",
  "enablePullDownRefresh": true,
  "usingComponents": {
    "my-card": "/components/card/card"
  }
}
```

### index.wxss

```css
.container {
  padding: 20rpx;
}

.title {
  font-size: 32rpx;
  font-weight: bold;
}

.item {
  padding: 20rpx;
  border-bottom: 1rpx solid #eee;
}
```

**rpx 单位**：响应式像素，750rpx = 屏幕宽度。永远不用 px。

## 常用模式

### 封装 wx.request 为 Promise

```javascript
// utils/request.js
function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      ...options,
      header: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${wx.getStorageSync('token')}`,
        ...options.header,
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else if (res.statusCode === 401) {
          wx.reLaunch({ url: '/pages/login/login' });
          reject(new Error('未授权'));
        } else {
          reject(new Error(res.data?.message || `HTTP ${res.statusCode}`));
        }
      },
      fail: reject,
    });
  });
}

module.exports = { request };
```

### 自定义组件

```javascript
// components/card/card.js
Component({
  properties: {
    title: { type: String, value: '' },
    count: { type: Number, value: 0 },
  },
  data: {
    expanded: false,
  },
  methods: {
    onToggle() {
      this.setData({ expanded: !this.data.expanded });
      this.triggerEvent('toggle', { expanded: !this.data.expanded });
    },
  },
});
```

父页面使用：
```xml
<my-card title="订单" count="{{orderCount}}" bind:toggle="onCardToggle" />
```

### 登录态管理

```javascript
// app.js
App({
  globalData: {
    userInfo: null,
    token: null,
  },

  async onLaunch() {
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
      try {
        const userInfo = await this.fetchUserInfo();
        this.globalData.userInfo = userInfo;
      } catch {
        wx.removeStorageSync('token');
      }
    }
  },

  async login() {
    const { code } = await wx.login();
    const res = await request({
      url: 'https://api.example.com/auth/wechat',
      method: 'POST',
      data: { code },
    });
    wx.setStorageSync('token', res.token);
    this.globalData.token = res.token;
    this.globalData.userInfo = res.userInfo;
  },
});
```

### 分包

```json
// app.json
{
  "pages": ["pages/index/index", "pages/profile/profile"],
  "subpackages": [
    {
      "root": "pages/order",
      "name": "order",
      "pages": ["list/list", "detail/detail"]
    }
  ],
  "preloadRule": {
    "pages/profile/profile": { "packages": ["order"] }
  }
}
```

## 常见陷阱

- **setData 性能**：避免一次 setData 超过 1MB；频繁 setData 会卡顿。用 diff 更新或防抖。
- **页面栈最多 10 层**：`wx.navigateTo` 超过会失败。深层流程用 `wx.redirectTo` 或 `wx.reLaunch`。
- **onShow 多次触发**：每次返回、tab 切换、从后台恢复都会触发。副作用要幂等。
- **图片域名白名单**：所有外部图片 URL 必须在「开发者平台」→「服务器域名」配置，否则真机加载不出来。
- **Storage 同步 vs 异步**：启动时别用 `wx.getStorageSync` 大量读（会阻塞），用 `wx.getStorage` async。

## 测试

官方没有完善的单测框架。推荐：

- **业务逻辑**：抽到 `utils/` 用 Node 环境的 Jest 跑
- **页面交互**：用 [miniprogram-simulate](https://github.com/wechat-miniprogram/miniprogram-simulate) 模拟页面和组件
- **真机回归**：微信开发者工具的「自动化测试」

## 工具链

- **开发者工具**：微信开发者工具（必装）
- **构建**：默认无构建，或用 `@vant/weapp` / `miniprogram-ci` 发布
- **Lint**：eslint + eslint-plugin-miniprogram
- **类型**：可选 TypeScript（官方支持），`.ts` 文件会被编译

## 禁止

- ❌ 用 `setData` 传大对象（应 diff 更新）
- ❌ 在 `onLoad` 里用 `setData` 前调用 `this.data.xxx`（此时 data 可能还没合并）
- ❌ 页面层级超过 10（会 navigateTo 失败）
- ❌ 跨页面直接读写另一个页面的 data（应通过 globalData / eventBus）
- ❌ 在 WXSS 里用 `!important` 覆盖平台样式（通常是用错了选择器优先级）
- ❌ 在 `onLaunch` 里做阻塞 IO（拉长启动时间）

## 参考

- 官方文档：https://developers.weixin.qq.com/miniprogram/dev/framework/
- API 列表：https://developers.weixin.qq.com/miniprogram/dev/api/
- 最佳实践：https://developers.weixin.qq.com/miniprogram/dev/framework/performance/
