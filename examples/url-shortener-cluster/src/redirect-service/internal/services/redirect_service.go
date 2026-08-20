package services

import (
	"context"
	"fmt"
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
		return err
	}
	s.routes[route.Code] = route
	_ = s.cache.Set(context.Background(), route.Code, route.TargetURL, 24*time.Hour)
	return nil
}

// ResolveRedirect handles high-throughput redirection (< 1ms).
func (s *RedirectService) ResolveRedirect(ctx context.Context, code string, ip, userAgent, referrer string) (string, error) {
	// 1. Fast path: Redis Cluster lookups
	targetURL, err := s.cache.Get(ctx, code)
	tenantID := "tenant-default"

	if err != nil || targetURL == "" {
		route, exists := s.routes[code]
		if !exists || !route.IsActive {
			return "", domain.ErrRouteNotFound
		}
		targetURL = route.TargetURL
		tenantID = route.TenantID
		_ = s.cache.Set(ctx, code, targetURL, 24*time.Hour)
	}

	s.totalServed.Add(1)

	// 2. Non-blocking asynchronous clickstream dispatch to Kafka stream bus
	telemetry := domain.ClickTelemetry{
		EventID:       fmt.Sprintf("evt_%d_%s", time.Now().UnixNano(), code),
		Code:          code,
		TenantID:      tenantID,
		TimestampNano: time.Now().UnixNano(),
		IPAddress:     ip,
		CountryCode:   "US",
		UserAgent:     userAgent,
		Referrer:      referrer,
	}

	_ = s.producer.ProduceClickEvent(ctx, telemetry)

	return targetURL, nil
}

func (s *RedirectService) GetTotalServed() int64 {
	return s.totalServed.Load()
}
