package data

import (
	"time"

	"github.com/lib/pq"
)

// userPO 用户持久化对象。表名默认复数 users。
type userPO struct {
	ID           int64     `gorm:"primaryKey;column:id"`
	Email        string    `gorm:"column:email;uniqueIndex;size:128;not null"`
	PasswordHash string    `gorm:"column:password_hash;size:128;not null"`
	Nickname     string    `gorm:"column:nickname;size:64;not null;default:''"`
	CreatedAt    time.Time `gorm:"column:created_at;autoCreateTime"`
	UpdatedAt    time.Time `gorm:"column:updated_at;autoUpdateTime"`
}

// TableName 显式声明表名。
func (userPO) TableName() string { return "users" }

// postPO 文章持久化对象。
type postPO struct {
	ID        int64          `gorm:"primaryKey;column:id"`
	AuthorID  int64          `gorm:"column:author_id;not null;index"`
	Title     string         `gorm:"column:title;size:256;not null"`
	Body      string         `gorm:"column:body;type:text;not null;default:''"`
	Tags      pq.StringArray `gorm:"column:tags;type:text[];not null;default:'{}'"`
	LikeCount int64          `gorm:"column:like_count;not null;default:0"`
	CreatedAt time.Time      `gorm:"column:created_at;autoCreateTime"`
	UpdatedAt time.Time      `gorm:"column:updated_at;autoUpdateTime"`
}

func (postPO) TableName() string { return "posts" }

// commentPO 评论持久化对象。
type commentPO struct {
	ID        int64     `gorm:"primaryKey;column:id"`
	PostID    int64     `gorm:"column:post_id;not null;index"`
	AuthorID  int64     `gorm:"column:author_id;not null"`
	Body      string    `gorm:"column:body;type:text;not null"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime"`
}

func (commentPO) TableName() string { return "comments" }

// postLikePO 点赞联合主键表。
type postLikePO struct {
	PostID    int64     `gorm:"primaryKey;column:post_id"`
	UserID    int64     `gorm:"primaryKey;column:user_id"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime"`
}

func (postLikePO) TableName() string { return "post_likes" }
