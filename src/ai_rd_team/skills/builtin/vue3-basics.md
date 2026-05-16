---
name: vue3-basics
description: Vue 3 + Composition API + Vite + TypeScript 前端开发基础（仅 Vue 3，不含 Vue 2 / Nuxt / SSR）。新建或扩展 Vue 3 SPA 时使用——覆盖单文件组件、`<script setup>`、Pinia 状态管理、可复用 composable、Vue Router、Vitest 单测，以及响应式陷阱（reactive 解构丢失、ref vs reactive 取舍）。
default_for: []
---

# Vue 3 Frontend Basics

## 适用场景

使用 Vue 3（Composition API）+ Vite + TypeScript 写 Web 前端。

## 核心原则

- **Composition API 优先**：`<script setup>` + `ref` / `reactive` / `computed`
- **TypeScript**：所有组件、props、emit、store 都带类型
- **单文件组件**：`.vue` 文件 = template + script + style，职责单一
- **组合式函数**：复用逻辑用 `useXxx()` composable，不用 Mixin
- **状态管理**：Pinia > Vuex（Vue 3 官方推荐）

## 典型目录结构

```
src/
├── main.ts               # 入口
├── App.vue               # 根组件
├── router/               # Vue Router 配置
│   └── index.ts
├── stores/               # Pinia stores
│   └── user.ts
├── composables/          # 可复用 composable
│   └── useFetch.ts
├── components/           # 通用组件
├── views/                # 页面（路由对应）
├── api/                  # 后端 API 封装
├── types/                # TypeScript 类型
└── utils/                # 工具函数
```

## 常用模式

### 单文件组件骨架

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

// props（必须带类型 + 默认值）
interface Props {
  userId: number;
  title?: string;
}
const props = withDefaults(defineProps<Props>(), { title: '未命名' });

// emits（带签名）
const emit = defineEmits<{
  (e: 'update', value: string): void;
  (e: 'close'): void;
}>();

// 状态
const count = ref(0);
const double = computed(() => count.value * 2);

// 方法
function handleClick() {
  count.value++;
  emit('update', `count=${count.value}`);
}

// 生命周期
onMounted(async () => {
  // ...
});
</script>

<template>
  <div class="card">
    <h2>{{ title }} (user={{ userId }})</h2>
    <p>count={{ count }} double={{ double }}</p>
    <button @click="handleClick">+1</button>
  </div>
</template>

<style scoped>
.card { padding: 1rem; border: 1px solid #ddd; }
</style>
```

### Pinia Store

```typescript
// stores/user.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { User } from '@/types';

export const useUserStore = defineStore('user', () => {
  const current = ref<User | null>(null);
  const isLoggedIn = computed(() => current.value !== null);

  async function login(email: string, password: string) {
    const res = await api.login({ email, password });
    current.value = res.user;
  }

  function logout() {
    current.value = null;
  }

  return { current, isLoggedIn, login, logout };
});
```

组件里用：
```vue
<script setup lang="ts">
import { useUserStore } from '@/stores/user';
const userStore = useUserStore();
</script>
<template>
  <div v-if="userStore.isLoggedIn">Hi {{ userStore.current?.name }}</div>
</template>
```

### Composable 复用逻辑

```typescript
// composables/useFetch.ts
import { ref, onMounted } from 'vue';

export function useFetch<T>(url: string) {
  const data = ref<T | null>(null);
  const loading = ref(true);
  const error = ref<Error | null>(null);

  onMounted(async () => {
    try {
      const res = await fetch(url);
      data.value = await res.json();
    } catch (e) {
      error.value = e as Error;
    } finally {
      loading.value = false;
    }
  });

  return { data, loading, error };
}
```

### 路由

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('@/views/Home.vue') },
    {
      path: '/users/:id',
      component: () => import('@/views/UserDetail.vue'),
      props: true,  // route param 自动作为 prop 传入
    },
    {
      path: '/admin',
      component: () => import('@/views/Admin.vue'),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  const user = useUserStore();
  if (to.meta.requiresAuth && !user.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } };
  }
});
```

## 测试

用 [Vitest](https://vitest.dev/)：

```typescript
// Counter.spec.ts
import { mount } from '@vue/test-utils';
import Counter from './Counter.vue';

test('increments on click', async () => {
  const wrapper = mount(Counter);
  await wrapper.find('button').trigger('click');
  expect(wrapper.find('.count').text()).toBe('1');
});
```

## 样式方案

| 方案 | 适用 |
|------|-----|
| `<style scoped>` | 组件私有样式，默认推荐 |
| Tailwind CSS | 大项目 / 团队协作，快速迭代 |
| UnoCSS | Tailwind 替代，更快、按需生成 |
| CSS Modules | 需要类名哈希隔离 |

## 工具链

- **构建**：Vite（开发 < 300ms 热更新，生产 Rollup 打包）
- **类型检查**：`vue-tsc --noEmit`
- **Lint**：`eslint --ext .vue,.ts src`
- **格式化**：Prettier（配合 eslint-config-prettier）
- **测试**：Vitest + @vue/test-utils

## 禁止

- ❌ 用 Options API（Vue 2 风格）新写组件
- ❌ 在 setup 里用 `this`
- ❌ `ref.value` 忘记写（TypeScript 会报错，编译前就能发现）
- ❌ 组件文件超过 300 行（应拆分子组件 + composable）
- ❌ 把响应式对象用 `JSON.stringify` 序列化存 localStorage（应先 `toRaw`）
- ❌ 生产环境开 `app.config.performance = true`

## 常见陷阱

- **ref vs reactive**：基本类型用 `ref`，对象用 `reactive`。`ref(object)` 也可以，但得用 `.value` 访问。
- **props 解构丢响应式**：`const { title } = props` 会丢！用 `toRefs(props)` 或直接 `props.title`。
- **watch vs watchEffect**：`watch` 显式指定依赖，`watchEffect` 自动收集依赖（更方便但不易看清触发条件）。
- **父子组件通信超过两层**：用 provide/inject 或 Pinia，不要层层 props。

## 参考

- Vue 3 官方：https://vuejs.org/guide/
- Composition API RFC：https://v3.vuejs.org/guide/composition-api-introduction.html
- Pinia：https://pinia.vuejs.org/
- Vue Router：https://router.vuejs.org/
