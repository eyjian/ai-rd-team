package auth

import (
	"context"
	"errors"
	"strings"
	"time"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/middleware"
	ktransport "github.com/go-kratos/kratos/v2/transport"
	"github.com/golang-jwt/jwt/v5"
)

// UserIDKey 转发自 biz 包，保证 middleware 写入与 biz 读取使用同一 key
var UserIDKey = biz.UserIDCtxKey

// Claims JWT 自定义 claims
type Claims struct {
	UserID int64  `json:"uid"`
	Email  string `json:"email"`
	jwt.RegisteredClaims
}

// GenerateToken 签发 token
func GenerateToken(secret string, userID int64, email string, expire time.Duration) (string, error) {
	if secret == "" {
		return "", errors.New("jwt secret is empty")
	}
	claims := Claims{
		UserID: userID,
		Email:  email,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(expire)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	t := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return t.SignedString([]byte(secret))
}

// ParseToken 解析 token
func ParseToken(secret, tokenStr string) (*Claims, error) {
	c := &Claims{}
	tok, err := jwt.ParseWithClaims(tokenStr, c, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(secret), nil
	})
	if err != nil {
		return nil, err
	}
	if !tok.Valid {
		return nil, errors.New("invalid token")
	}
	return c, nil
}

// WithUserID 将 user_id 放入 ctx
func WithUserID(ctx context.Context, userID int64) context.Context {
	return context.WithValue(ctx, UserIDKey, userID)
}

// UserIDFromContext 从 ctx 读取 user_id；不存在返回 0 + false
func UserIDFromContext(ctx context.Context) (int64, bool) {
	v := ctx.Value(UserIDKey)
	if v == nil {
		return 0, false
	}
	id, ok := v.(int64)
	return id, ok
}

// MustUserIDFromContext 读不到则返回 401 错误
func MustUserIDFromContext(ctx context.Context) (int64, error) {
	id, ok := UserIDFromContext(ctx)
	if !ok || id == 0 {
		return 0, v1.ErrorUserUnauthenticated("missing user in context")
	}
	return id, nil
}

// JWTMiddleware 鉴权中间件
// 从 Authorization: Bearer xxx 解析 token 注入 ctx
// 对于白名单 operation（如 Register/Login/Get/List）跳过
func JWTMiddleware(secret string, skipOps map[string]struct{}) middleware.Middleware {
	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req any) (any, error) {
			// 判断是否跳过
			if tr, ok := ktransport.FromServerContext(ctx); ok {
				if _, skip := skipOps[tr.Operation()]; skip {
					// 但仍然尝试 parse（若带了 token 就挂 user_id），失败不报错
					if authH := tr.RequestHeader().Get("Authorization"); authH != "" {
						if token := stripBearer(authH); token != "" {
							if c, err := ParseToken(secret, token); err == nil {
								ctx = WithUserID(ctx, c.UserID)
							}
						}
					}
					return handler(ctx, req)
				}
				authH := tr.RequestHeader().Get("Authorization")
				if authH == "" {
					return nil, v1.ErrorUserUnauthenticated("missing Authorization header")
				}
				token := stripBearer(authH)
				if token == "" {
					return nil, v1.ErrorUserUnauthenticated("invalid Authorization header")
				}
				c, err := ParseToken(secret, token)
				if err != nil {
					return nil, v1.ErrorUserUnauthenticated("invalid token: %s", err.Error())
				}
				ctx = WithUserID(ctx, c.UserID)
			}
			return handler(ctx, req)
		}
	}
}

func stripBearer(h string) string {
	const prefix = "Bearer "
	if len(h) > len(prefix) && strings.EqualFold(h[:len(prefix)], prefix) {
		return strings.TrimSpace(h[len(prefix):])
	}
	// 有些客户端可能直接传 token
	return strings.TrimSpace(h)
}
