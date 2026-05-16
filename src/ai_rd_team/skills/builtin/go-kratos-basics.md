---
name: go-kratos-basics
description: Go + Kratos 后端开发基础。在使用 go-kratos 框架开发 gRPC/HTTP 后端服务时使用，覆盖分层目录（api/biz/data/service）、proto 优先、wire 依赖注入、错误处理、单测与集成测试等核心约定。
default_for: []
---

# Go + Kratos Backend Basics

## 适用场景

使用 [go-kratos](https://go-kratos.dev/) 框架写 Go 后端服务（gRPC + HTTP）。

## 核心原则

- **分层清晰**：`api/` (proto) → `internal/service/` → `internal/biz/` → `internal/data/`
- **proto 优先**：接口契约由 `.proto` 文件定义，生成 Go 代码而非手写
- **依赖注入**：用 `wire` 管理依赖图，不用全局变量 / 包级 init
- **配置外置**：`configs/config.yaml` + 环境变量覆盖，不硬编码

## 典型目录结构

```
cmd/<app>/          # main.go + wire 装配
api/<app>/v1/       # *.proto + 生成的 *.pb.go
configs/            # config.yaml
internal/
├── biz/            # 业务逻辑（对 data 层解耦的接口）
├── conf/           # 配置结构体（由 proto 生成）
├── data/           # 数据访问（GORM / Ent / Redis）
├── server/         # HTTP / gRPC server 装配
└── service/        # 协议层（biz ↔ API 映射）
```

## 常用模式

### Proto 定义

```protobuf
syntax = "proto3";
package api.user.v1;
option go_package = "my/api/user/v1;v1";

import "google/api/annotations.proto";

service UserService {
  rpc GetUser(GetUserRequest) returns (User) {
    option (google.api.http) = { get: "/v1/users/{id}" };
  }
}
```

然后 `kratos proto client api/user/v1/user.proto` 生成 HTTP + gRPC handler。

### biz 层（业务逻辑）

```go
type UserRepo interface {
    Get(ctx context.Context, id int64) (*User, error)
    // ... Save/Delete/List
}

type UserUsecase struct {
    repo UserRepo
    log  *log.Helper
}

func NewUserUsecase(repo UserRepo, logger log.Logger) *UserUsecase {
    return &UserUsecase{repo: repo, log: log.NewHelper(logger)}
}

func (uc *UserUsecase) Get(ctx context.Context, id int64) (*User, error) {
    return uc.repo.Get(ctx, id)
}
```

**biz 层只依赖接口**（`UserRepo`），不依赖具体 DB 实现，方便 mock 单测。

### data 层（实现接口）

```go
type userRepo struct {
    data *Data
    log  *log.Helper
}

func NewUserRepo(data *Data, logger log.Logger) biz.UserRepo {
    return &userRepo{data: data, log: log.NewHelper(logger)}
}

func (r *userRepo) Get(ctx context.Context, id int64) (*biz.User, error) {
    var po User  // GORM model
    if err := r.data.db.WithContext(ctx).Where("id=?", id).First(&po).Error; err != nil {
        return nil, err
    }
    return &biz.User{ID: po.ID, Name: po.Name}, nil
}
```

### service 层（协议映射）

```go
type UserService struct {
    v1.UnimplementedUserServiceServer
    uc *biz.UserUsecase
}

func (s *UserService) GetUser(ctx context.Context, req *v1.GetUserRequest) (*v1.User, error) {
    u, err := s.uc.Get(ctx, req.Id)
    if err != nil {
        return nil, err
    }
    return &v1.User{Id: u.ID, Name: u.Name}, nil
}
```

## 错误处理

用 Kratos 统一错误码：

```go
import "github.com/go-kratos/kratos/v2/errors"

return nil, errors.NotFound("USER_NOT_FOUND", "user %d does not exist", id)
```

前端拿到 HTTP 404 + JSON `{code: "USER_NOT_FOUND", message: "..."}`。

## 测试

### biz 层单测（mock repo）

```go
import "github.com/stretchr/testify/mock"

type MockUserRepo struct{ mock.Mock }

func (m *MockUserRepo) Get(ctx context.Context, id int64) (*biz.User, error) {
    args := m.Called(ctx, id)
    return args.Get(0).(*biz.User), args.Error(1)
}

func TestUserUsecase_Get(t *testing.T) {
    repo := new(MockUserRepo)
    repo.On("Get", mock.Anything, int64(1)).Return(&biz.User{ID: 1, Name: "alice"}, nil)

    uc := biz.NewUserUsecase(repo, log.DefaultLogger)
    u, err := uc.Get(context.Background(), 1)
    assert.NoError(t, err)
    assert.Equal(t, "alice", u.Name)
}
```

### 集成测试（跑真 DB）

- 用 `testcontainers-go` 拉一个 PostgreSQL
- 迁移 schema
- 测 data 层 + biz 层端到端

## 工具链

- **proto 生成**：`kratos proto client <.proto>`
- **依赖注入**：`wire ./cmd/<app>`
- **测试**：`go test ./... -race -cover`
- **lint**：`golangci-lint run`
- **构建**：`make build`（Kratos 模板自带）

## 禁止

- ❌ biz 层直接 import gorm（应通过 data 层的接口）
- ❌ service 层写业务逻辑（应在 biz 层）
- ❌ 在 data 层返回 PO 给 service（应在 data 层映射为 biz 模型）
- ❌ 用 `panic` 代替 error 返回
- ❌ 忽略 `err`（`_ = someFunc()`）

## 参考

- 官方文档：https://go-kratos.dev/
- 模板仓库：https://github.com/go-kratos/kratos-layout
- 错误规范：https://go-kratos.dev/docs/component/errors/
