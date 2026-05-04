// Package data 提供基础设施层实现：GORM 连接与各 Repo。
// data 层依赖 biz 定义的接口并返回 biz DO（不暴露 GORM 模型）。
package data

import (
	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
)

// ProviderSet is data providers.
var ProviderSet = wire.NewSet(
	NewData,
	NewUserRepo,
	NewPostRepo,
	NewCommentRepo,
	NewPostLikeRepo,
)

// Data 聚合数据层依赖（DB 句柄、日志等）。
type Data struct {
	db  *gorm.DB
	log *log.Helper
}

// NewData 初始化 GORM + PostgreSQL 连接。
// cleanup 由 wire 调用，进程退出时关闭底层连接。
func NewData(c *conf.Data, logger log.Logger) (*Data, func(), error) {
	lh := log.NewHelper(log.With(logger, "module", "data"))

	gormCfg := &gorm.Config{
		Logger: gormlogger.Default.LogMode(gormlogger.Warn),
	}

	db, err := gorm.Open(postgres.Open(c.Database.Source), gormCfg)
	if err != nil {
		return nil, nil, err
	}

	sqlDB, err := db.DB()
	if err != nil {
		return nil, nil, err
	}
	sqlDB.SetMaxOpenConns(20)
	sqlDB.SetMaxIdleConns(5)

	d := &Data{db: db, log: lh}
	cleanup := func() {
		lh.Info("closing data resources")
		if sdb, err := d.db.DB(); err == nil {
			_ = sdb.Close()
		}
	}
	return d, cleanup, nil
}
