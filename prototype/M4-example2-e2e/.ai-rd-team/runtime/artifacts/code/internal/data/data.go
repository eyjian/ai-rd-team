// Package data 提供 biz.*Repo 的 GORM 实现。
//
// 关键约束：
//   - 对上 **只返回 biz 领域模型**，严禁把 GORM PO 暴露给 biz 层；
//   - PO 结构体只在 data 包内可见（小写或放在本包）；
//   - 所有 Repo 共享一个 *gorm.DB，由 Data.DB 持有。
package data

import (
	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
)

// ProviderSet 供顶层 wire 使用：提供 *Data 以及三个 Repo 实现绑定到 biz 接口。
var ProviderSet = wire.NewSet(
	NewData,
	NewUserRepo,
	NewPostRepo,
	NewCommentRepo,
)

// Data 聚合存储层依赖，本期只有 *gorm.DB。
type Data struct {
	DB  *gorm.DB
	log *log.Helper
}

// NewData 构造函数，返回 cleanup 供 kratos app 关闭时释放连接池。
func NewData(c *conf.Data, logger log.Logger) (*Data, func(), error) {
	helper := log.NewHelper(log.With(logger, "module", "data"))

	db, err := gorm.Open(postgres.Open(c.GetDatabase().GetSource()), &gorm.Config{
		Logger: gormlogger.Default.LogMode(gormlogger.Warn),
	})
	if err != nil {
		return nil, nil, err
	}
	sqlDB, err := db.DB()
	if err != nil {
		return nil, nil, err
	}
	sqlDB.SetMaxOpenConns(50)
	sqlDB.SetMaxIdleConns(10)

	cleanup := func() {
		helper.Info("closing database connection")
		if sqldb, err := db.DB(); err == nil {
			_ = sqldb.Close()
		}
	}
	return &Data{DB: db, log: helper}, cleanup, nil
}
