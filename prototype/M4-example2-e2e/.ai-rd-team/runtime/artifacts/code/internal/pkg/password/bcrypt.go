// Package password 封装密码散列 / 校验，内部使用 bcrypt。
//
// 测试环境可调用 SetTestCost(4) 以加速单测。生产默认 bcrypt.DefaultCost。
package password

import "golang.org/x/crypto/bcrypt"

// 当前 bcrypt 的 cost，默认跟随 bcrypt.DefaultCost。
var cost = bcrypt.DefaultCost

// SetTestCost 调整 bcrypt 的 cost，仅供测试使用。
func SetTestCost(c int) {
	if c < bcrypt.MinCost || c > bcrypt.MaxCost {
		return
	}
	cost = c
}

// Hash 计算密码散列。
func Hash(plain string) (string, error) {
	b, err := bcrypt.GenerateFromPassword([]byte(plain), cost)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

// Verify 校验密码与散列是否匹配。
func Verify(hash, plain string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(plain)) == nil
}
