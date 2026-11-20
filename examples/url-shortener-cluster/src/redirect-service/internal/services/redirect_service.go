package services

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"sync/atomic"
	"time"

	"redirect-service/internal/domain"
	"redirect-service/internal/ports"
)

type RedirectService struct {
	cache    ports.IRedisCachePort
	producer ports.IKafkaProducerPort
	// routes is an in-memory mock standing in for the ADR-001 Redis-cluster read
	// path with asynchronous PostgreSQL fallback on cache-miss (see
	// docs/architecture/ADR-001-distributed-storage-stack.md): the real
	// implementation would hydrate this map from PostgreSQL on cache miss.
	mu          sync.RWMutex
	routes      map[string]domain.RedirectRoute
	totalServed atomic.Int64
}

func NewRedirectService(cache ports.IRedisCachePort, producer ports.IKafkaProducerPort) *RedirectService {
	return &RedirectService{
		cache:    cache,
		producer: producer,
		routes:   make(map[string]domain.RedirectRoute),
	}
}

func (s *RedirectService) RegisterRoute(route domain.RedirectRoute) error {
	if err := route.Validate(); err != nil {
		slog.Warn("rejected invalid redirect route", "code", route.Code, "error", err)
		return err
	}
	s.mu.Lock()
	s.routes[route.Code] = route
	s.mu.Unlock()
	_ = s.cache.Set(context.Background(), route.Code, route.TargetURL, 24*time.Hour)
	slog.Info("registered redirect route", "code", route.Code, "tenant_id", route.TenantID)
	return nil
}

// ResolveRedirect handles high-throughput redirection (< 1ms).
func (s *RedirectService) ResolveRedirect(ctx context.Context, code string, ip, userAgent, referrer string) (string, error) {
	// 1. Fast path: Redis Cluster lookups
	targetURL, err := s.cache.Get(ctx, code)
	tenantID := "tenant-default"

	s.mu.RLock()
	route, exists := s.routes[code]
	s.mu.RUnlock()
	if exists && route.TenantID != "" {
		tenantID = route.TenantID
	}

	if err != nil || targetURL == "" {
		if !exists || !route.IsActive {
			slog.Warn("redirect route lookup failed", "code", code)
			return "", domain.ErrRouteNotFound
		}
		targetURL = route.TargetURL
		_ = s.cache.Set(ctx, code, targetURL, 24*time.Hour)
	}

	s.totalServed.Add(1)

	// 2. Non-blocking asynchronous CloudEvents 1.0.2 clickstream dispatch to Kafka stream bus
	telemetry := domain.ClickTelemetry{
		SpecVersion:   "1.0",
		Source:        "/krypton/redirect-service",
		Type:          "com.krypton.redirect.clicked",
		EventID:       fmt.Sprintf("evt_%d_%s", time.Now().UnixNano(), code),
		Code:          code,
		TenantID:      tenantID,
		TimestampNano: time.Now().UnixNano(),
		IPAddress:     ip,
		CountryCode:   "US",
		UserAgent:     userAgent,
		Referrer:      referrer,
	}

	if err := s.producer.ProduceClickEvent(ctx, telemetry); err != nil {
		slog.Warn("failed to enqueue click telemetry", "code", code, "error", err)
	}

	return targetURL, nil
}

func (s *RedirectService) GetTotalServed() int64 {
	return s.totalServed.Load()
}
