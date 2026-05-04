package data

import (
	"strings"

	"github.com/jackc/pgconn"
)

// isUniqueViolation 判断是否为 PostgreSQL 唯一索引冲突（SQLSTATE 23505）。
// 同时兼容错误链中包装的情况，以及字符串回退。
func isUniqueViolation(err error) bool {
	if err == nil {
		return false
	}
	var pgErr *pgconn.PgError
	if asPgErr(err, &pgErr) && pgErr.Code == "23505" {
		return true
	}
	return strings.Contains(err.Error(), "SQLSTATE 23505") ||
		strings.Contains(err.Error(), "duplicate key value violates unique constraint")
}

// asPgErr 封装 errors.As 以避免在每个 Repo 中重复 import。
func asPgErr(err error, target **pgconn.PgError) bool {
	for e := err; e != nil; {
		if pg, ok := e.(*pgconn.PgError); ok {
			*target = pg
			return true
		}
		type unwrapper interface{ Unwrap() error }
		u, ok := e.(unwrapper)
		if !ok {
			return false
		}
		e = u.Unwrap()
	}
	return false
}
