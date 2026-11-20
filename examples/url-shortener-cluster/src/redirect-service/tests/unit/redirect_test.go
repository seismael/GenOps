package unit_test

import (
	"context"
	"sync"
	"testing"
	"time"

	"redirect-service/internal/adapters/cache"
	"redirect-service/internal/adapters/streaming"
	"redirect-service/internal/domain"
	"redirect-service/internal/services"
)

func TestDomainInvariantsAndSSRF(t *testing.T) {
	validRoute := domain.RedirectRoute{
		Code:      "blackfriday",
		TargetURL: "https://shop.acme.com/deals",
		TenantID:  "tenant_100",
		IsActive:  true,
	}
	if err := validRoute.Validate(); err != nil {
		t.Fatalf("expected valid route, got error: %v", err)
	}

	ssrfCases := []string{
		"http://127.0.0.1/admin",
		"http://LOCALHOST/admin",
		"http://localhost./admin",
		"http://sub.localhost/admin",
	}
	for _, target := range ssrfCases {
		ssrfRoute := domain.RedirectRoute{
			Code:      "badssrf",
			TargetURL: target,
			TenantID:  "tenant_100",
			IsActive:  true,
		}
		if err := ssrfRoute.Validate(); err == nil {
			t.Fatalf("expected SSRF error for %s, got nil", target)
		}
	}
}

func TestConcurrentRedirectionAndTelemetryThroughput(t *testing.T) {
	redisCluster := cache.NewMemoryRedisCluster()
	kafkaProducer := streaming.NewAsyncKafkaProducer(50000)
	defer kafkaProducer.Close()
	svc := services.NewRedirectService(redisCluster, kafkaProducer)

	route := domain.RedirectRoute{
		Code:      "hyperscale",
		TargetURL: "https://cloud.acme.com/landing",
		TenantID:  "tenant_enterprise",
		IsActive:  true,
	}
	if err := svc.RegisterRoute(route); err != nil {
		t.Fatalf("failed to register route: %v", err)
	}

	concurrency := 20000
	var wg sync.WaitGroup
	wg.Add(concurrency)

	start := time.Now()
	for i := 0; i < concurrency; i++ {
		go func(id int) {
			defer wg.Done()
			target, err := svc.ResolveRedirect(context.Background(), "hyperscale", "198.51.100.4", "Mozilla/5.0", "https://news.ycombinator.com")
			if err != nil || target != "https://cloud.acme.com/landing" {
				t.Errorf("redirect failed: target=%s, err=%v", target, err)
			}
		}(i)
	}

	wg.Wait()
	duration := time.Since(start)

	t.Logf("Successfully served %d concurrent redirects in %v (Throughput: %.2f ops/sec)", concurrency, duration, float64(concurrency)/duration.Seconds())

	if svc.GetTotalServed() != int64(concurrency) {
		t.Fatalf("expected %d served, got %d", concurrency, svc.GetTotalServed())
	}
	kafkaProducer.Close()
	if kafkaProducer.GetProducedCount() == 0 {
		t.Fatalf("expected produced telemetry events > 0, got 0")
	}
}
