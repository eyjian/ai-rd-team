package integration

import "strconv"

// pathPost 返回 /v1/posts/{id}
func pathPost(id int64) string {
	return "/v1/posts/" + strconv.FormatInt(id, 10)
}

// pathComments 返回 /v1/posts/{post_id}/comments
func pathComments(postID int64) string {
	return "/v1/posts/" + strconv.FormatInt(postID, 10) + "/comments"
}

// pathLike 返回 /v1/posts/{post_id}/like
func pathLike(postID int64) string {
	return "/v1/posts/" + strconv.FormatInt(postID, 10) + "/like"
}
