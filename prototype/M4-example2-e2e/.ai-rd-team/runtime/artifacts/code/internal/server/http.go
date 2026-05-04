package server

import (
	"context"
	"net/http"
	"strconv"
	"strings"

	v1 "blog/api/blog/v1"
	"blog/internal/conf"
	"blog/internal/pkg/auth"
	"blog/internal/service"

	kerr "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/middleware/selector"
	"github.com/go-kratos/kratos/v2/transport"
	khttp "github.com/go-kratos/kratos/v2/transport/http"
)

// NewHTTPServer builds the kratos HTTP server with all routes registered.
func NewHTTPServer(
	c *conf.Server,
	userSvc *service.UserService,
	postSvc *service.PostService,
	commentSvc *service.CommentService,
	jwt *auth.JWTIssuer,
	logger log.Logger,
) *khttp.Server {
	authMW := selector.Server(auth.Middleware(jwt)).Match(publicMatch).Build()

	var opts []khttp.ServerOption
	opts = append(opts, khttp.Middleware(
		recovery.Recovery(),
		logging.Server(logger),
		authMW,
	))
	if c != nil && c.GetHttp() != nil {
		if addr := c.GetHttp().GetAddr(); addr != "" {
			opts = append(opts, khttp.Address(addr))
		}
		if to := c.GetHttp().GetTimeout(); to > 0 {
			opts = append(opts, khttp.Timeout(to))
		}
	}
	srv := khttp.NewServer(opts...)

	r := srv.Route("/")
	// user/auth
	r.POST("/v1/users", wrapRegister(userSvc))
	r.POST("/v1/auth/login", wrapLogin(userSvc))
	r.GET("/v1/users/me", wrapGetMe(userSvc))
	// posts
	r.POST("/v1/posts", wrapCreatePost(postSvc))
	r.GET("/v1/posts", wrapListPosts(postSvc))
	r.GET("/v1/posts/{id}", wrapGetPost(postSvc))
	r.PUT("/v1/posts/{id}", wrapUpdatePost(postSvc))
	r.DELETE("/v1/posts/{id}", wrapDeletePost(postSvc))
	r.POST("/v1/posts/{id}/like", wrapLikePost(postSvc))
	r.DELETE("/v1/posts/{id}/like", wrapUnlikePost(postSvc))
	// comments
	r.POST("/v1/posts/{id}/comments", wrapCreateComment(commentSvc))
	r.GET("/v1/posts/{id}/comments", wrapListComments(commentSvc))

	return srv
}

// publicMatch returns true when the current request SHOULD have auth middleware applied.
// Return false to skip auth (public routes).
func publicMatch(ctx context.Context, _ string) bool {
	tr, ok := transport.FromServerContext(ctx)
	if !ok {
		return true
	}
	if tr.Kind() != transport.KindHTTP {
		return true
	}
	hi, ok := tr.(khttp.Transporter)
	if !ok {
		return true
	}
	req := hi.Request()
	if req == nil {
		return true
	}
	method := req.Method
	path := req.URL.Path
	// Public endpoints (skip auth => return false here).
	if method == http.MethodPost && path == "/v1/users" {
		return false
	}
	if method == http.MethodPost && path == "/v1/auth/login" {
		return false
	}
	if method == http.MethodGet && strings.HasPrefix(path, "/v1/posts") {
		return false
	}
	return true
}

// ---------- HTTP handler wrappers ----------

func wrapRegister(s *service.UserService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		in := &v1.RegisterRequest{}
		if err := ctx.Bind(in); err != nil {
			return badRequest(err)
		}
		out, err := s.Register(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapLogin(s *service.UserService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		in := &v1.LoginRequest{}
		if err := ctx.Bind(in); err != nil {
			return badRequest(err)
		}
		out, err := s.Login(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapGetMe(s *service.UserService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		out, err := s.GetMe(ctx, &v1.GetMeRequest{})
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapCreatePost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		in := &v1.CreatePostRequest{}
		if err := ctx.Bind(in); err != nil {
			return badRequest(err)
		}
		out, err := s.CreatePost(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapGetPost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		id, err := pathID(ctx)
		if err != nil {
			return err
		}
		out, err := s.GetPost(ctx, &v1.GetPostRequest{Id: id})
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapListPosts(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		q := ctx.Request().URL.Query()
		in := &v1.ListPostsRequest{Tag: q.Get("tag")}
		if v := q.Get("page"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				in.Page = int32(n)
			}
		}
		if v := q.Get("size"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				in.Size = int32(n)
			}
		}
		out, err := s.ListPosts(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapUpdatePost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		in := &v1.UpdatePostRequest{}
		if err := ctx.Bind(in); err != nil {
			return badRequest(err)
		}
		id, err := pathID(ctx)
		if err != nil {
			return err
		}
		in.Id = id
		out, err := s.UpdatePost(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapDeletePost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		id, err := pathID(ctx)
		if err != nil {
			return err
		}
		out, err := s.DeletePost(ctx, &v1.DeletePostRequest{Id: id})
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapLikePost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		id, err := pathID(ctx)
		if err != nil {
			return err
		}
		out, err := s.LikePost(ctx, &v1.LikePostRequest{Id: id})
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapUnlikePost(s *service.PostService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		id, err := pathID(ctx)
		if err != nil {
			return err
		}
		out, err := s.UnlikePost(ctx, &v1.UnlikePostRequest{Id: id})
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapCreateComment(s *service.CommentService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		in := &v1.CreateCommentRequest{}
		if err := ctx.Bind(in); err != nil {
			return badRequest(err)
		}
		pid, err := pathID(ctx)
		if err != nil {
			return err
		}
		in.PostId = pid
		out, err := s.CreateComment(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

func wrapListComments(s *service.CommentService) khttp.HandlerFunc {
	return func(ctx khttp.Context) error {
		pid, err := pathID(ctx)
		if err != nil {
			return err
		}
		in := &v1.ListCommentsRequest{PostId: pid}
		q := ctx.Request().URL.Query()
		if v := q.Get("page"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				in.Page = int32(n)
			}
		}
		if v := q.Get("size"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				in.Size = int32(n)
			}
		}
		out, err := s.ListComments(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(http.StatusOK, out)
	}
}

// ---------- helpers ----------

func pathID(ctx khttp.Context) (int64, error) {
	idStr := ctx.Vars().Get("id")
	if idStr == "" {
		return 0, kerr.BadRequest(v1.ReasonValidationFailed, "missing path id")
	}
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		return 0, kerr.BadRequest(v1.ReasonValidationFailed, "invalid path id")
	}
	return id, nil
}

func badRequest(err error) error {
	return kerr.BadRequest(v1.ReasonValidationFailed, err.Error())
}
