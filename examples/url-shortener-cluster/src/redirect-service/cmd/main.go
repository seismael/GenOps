package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"redirect-service/internal/adapters/cache"
	"redirect-service/internal/adapters/streaming"
	"redirect-service/internal/domain"
	"redirect-service/internal/services"
)

type registerRouteRequest struct {
	Code      string `json:"code"`
	TargetURL string `json:"target_url"`
	TenantID  string `json:"tenant_id"`
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func main() {
	redisCache := cache.NewMemoryRedisCluster()
	kafkaProducer := streaming.NewAsyncKafkaProducer(4096)
	defer kafkaProducer.Close()

	svc := services.NewRedirectService(redisCache, kafkaProducer)
	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "healthy",
			"service": "redirect-service",
			"version": "1.0.0",
		})
	})

	mux.HandleFunc("POST /api/v1/routes", func(w http.ResponseWriter, r *http.Request) {
		var req registerRouteRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"type":   "urn:krypton:problem:invalid-json",
				"title":  "Invalid JSON Request",
				"status": http.StatusBadRequest,
				"detail": err.Error(),
			})
			return
		}
		route := domain.RedirectRoute{
			Code:      strings.TrimSpace(req.Code),
			TargetURL: strings.TrimSpace(req.TargetURL),
			TenantID:  strings.TrimSpace(req.TenantID),
			IsActive:  true,
			CreatedAt: time.Now().UTC(),
		}
		if err := svc.RegisterRoute(route); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"type":   "urn:krypton:problem:validation-error",
				"title":  "Invalid Redirect Route",
				"status": http.StatusBadRequest,
				"detail": err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusCreated, map[string]any{
			"code":       route.Code,
			"target_url": route.TargetURL,
			"tenant_id":  route.TenantID,
		})
	})

	mux.HandleFunc("GET /{code}", func(w http.ResponseWriter, r *http.Request) {
		code := r.PathValue("code")
		target, err := svc.ResolveRedirect(
			r.Context(),
			code,
			r.RemoteAddr,
			r.UserAgent(),
			r.Referer(),
		)
		if err != nil {
			statusCode := http.StatusNotFound
			if !errors.Is(err, domain.ErrRouteNotFound) {
				statusCode = http.StatusBadRequest
			}
			writeJSON(w, statusCode, map[string]any{
				"type":   "urn:krypton:problem:not-found",
				"title":  "Route Resolution Failed",
				"status": statusCode,
				"detail": err.Error(),
			})
			return
		}
		http.Redirect(w, r, target, http.StatusFound)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		slog.Info("redirect-service listening", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("redirect-service server failed", "error", err)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
	slog.Info("redirect-service stopped cleanly")
}
