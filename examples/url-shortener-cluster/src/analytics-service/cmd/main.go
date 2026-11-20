package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"analytics-service/internal/adapters/persistence"
	"analytics-service/internal/domain"
	"analytics-service/internal/services"
)

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func main() {
	store := persistence.NewInMemColumnarClickHouse()
	svc := services.NewAnalyticsService(store)
	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "healthy",
			"service": "analytics-service",
			"version": "1.0.0",
		})
	})

	mux.HandleFunc("POST /api/v1/analytics/ingest", func(w http.ResponseWriter, r *http.Request) {
		var records []domain.ClickRecord
		if err := json.NewDecoder(r.Body).Decode(&records); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"type":   "urn:krypton:problem:invalid-json",
				"title":  "Invalid Batch Payload",
				"status": http.StatusBadRequest,
				"detail": err.Error(),
			})
			return
		}
		if err := svc.IngestBatch(r.Context(), records); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{
				"type":   "urn:krypton:problem:ingest-failed",
				"title":  "Analytics Ingestion Failed",
				"status": http.StatusInternalServerError,
				"detail": err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusAccepted, map[string]int{"ingested": len(records)})
	})

	mux.HandleFunc("GET /api/v1/analytics/{code}", func(w http.ResponseWriter, r *http.Request) {
		code := r.PathValue("code")
		tenantID := r.URL.Query().Get("tenant_id")
		query := domain.MetricQuery{
			Code:      code,
			TenantID:  tenantID,
			StartTime: time.Now().UTC().Add(-24 * time.Hour),
			EndTime:   time.Now().UTC(),
			GroupBy:   "referrer",
		}
		report, err := svc.QueryCampaignAnalytics(r.Context(), query)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{
				"type":   "urn:krypton:problem:query-failed",
				"title":  "Analytics Query Failed",
				"status": http.StatusInternalServerError,
				"detail": err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusOK, report)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
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
		slog.Info("analytics-service listening", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("analytics-service server failed", "error", err)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
	slog.Info("analytics-service stopped cleanly")
}
