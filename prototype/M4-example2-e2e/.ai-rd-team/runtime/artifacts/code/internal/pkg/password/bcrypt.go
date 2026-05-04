// Package password 封装密码哈希与校验，统一使用 bcrypt。
package password

import "golang.org/x/crypto/bcrypt"

// DefaultCost 默认 bcrypt cost。
const DefaultCost = 10

// Hash 生成 bcrypt 哈希。
func Hash(plain string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(plain), DefaultCost)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// Verify 校验明文密码与 bcrypt 哈希是否匹配。
// 返回 true 表示匹配；任何错误都视为不匹配（不泄漏原因）。
func Verify(hash, plain string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(plain)) == nil
}
