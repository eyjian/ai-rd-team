// Package auth provides JWT issuer and Kratos middleware for BlogAPI.
package auth

import (
	"context"
	"strconv"
	"time"

	"blog/internal/conf"

	kerr "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/transport"
	jwtv5 "github.com/golang-jwt/jwt/v5"
	"github.com/google/wire"
)

// ProviderSet exposes the JWTIssuer + middleware to wire.
var ProviderSet = wire.NewSet(NewJWTIssuer)

// UserIDKey is the typed context key holding authenticated user id.
type UserIDKey struct{}

// ErrUnauthorized is the canonical kratos error for missing/invalid token.
func ErrUnauthorized(reason string) error {
	if reason == "" {
		reason = "UNAUTHORIZED"
	}
	return kerr.Unauthorized(reason, "authentication required")
}

// JWTIssuer signs and parses JWT tokens.
type JWTIssuer struct {
	Secret string
	TTL    time.Duration
}

// NewJWTIssuer builds an issuer from conf.Auth.
func NewJWTIssuer(c *conf.Auth) *JWTIssuer {
	ttl := 24 * time.Hour
	if c != nil && c.GetAccessTtl() > 0 {
		ttl = c.GetAccessTtl()
	}
	secret := ""
	if c != nil {
		secret = c.GetJwtSecret()
	}
	return &JWTIssuer{Secret: secret, TTL: ttl}
}

// Sign issues a JWT for the given user id.
func (j *JWTIssuer) Sign(userID int64) (string, error) {
	claims := jwtv5.MapClaims{
		"sub": strconv.FormatInt(userID, 10),
		"exp": time.Now().Add(j.TTL).Unix(),
		"iat": time.Now().Unix(),
	}
	tok := jwtv5.NewWithClaims(jwtv5.SigningMethodHS256, claims)
	return tok.SignedString([]byte(j.Secret))
}

// Parse validates the token string and extracts user id.
func (j *JWTIssuer) Parse(tokenString string) (int64, error) {
	tok, err := jwtv5.Parse(tokenString, func(t *jwtv5.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwtv5.SigningMethodHMAC); !ok {
			return nil, ErrUnauthorized("UNAUTHORIZED")
		}
		return []byte(j.Secret), nil
	})
	if err != nil || !tok.Valid {
		return 0, ErrUnauthorized("UNAUTHORIZED")
	}
	claims, ok := tok.Claims.(jwtv5.MapClaims)
	if !ok {
		return 0, ErrUnauthorized("UNAUTHORIZED")
	}
	sub, ok := claims["sub"].(string)
	if !ok {
		return 0, ErrUnauthorized("UNAUTHORIZED")
	}
	uid, err := strconv.ParseInt(sub, 10, 64)
	if err != nil {
		return 0, ErrUnauthorized("UNAUTHORIZED")
	}
	return uid, nil
}

// WithUserID returns a new context carrying the authenticated user id.
func WithUserID(ctx context.Context, uid int64) context.Context {
	return context.WithValue(ctx, UserIDKey{}, uid)
}

// UserIDFromContext returns the authenticated user id or (0,false).
func UserIDFromContext(ctx context.Context) (int64, bool) {
	v := ctx.Value(UserIDKey{})
	if v == nil {
		return 0, false
	}
	uid, ok := v.(int64)
	return uid, ok
}

// Middleware is a Kratos middleware that validates Authorization: Bearer <jwt>
// and injects user id into context. Callers wrap it with selector.Server.Match.
func Middleware(j *JWTIssuer) middleware.Middleware {
	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req interface{}) (interface{}, error) {
			tr, ok := transport.FromServerContext(ctx)
			if !ok {
				return nil, ErrUnauthorized("UNAUTHORIZED")
			}
			authz := tr.RequestHeader().Get("Authorization")
			if len(authz) < 8 || authz[:7] != "Bearer " {
				return nil, ErrUnauthorized("UNAUTHORIZED")
			}
			uid, err := j.Parse(authz[7:])
			if err != nil {
				return nil, err
			}
			ctx = WithUserID(ctx, uid)
			return handler(ctx, req)
		}
	}
}
