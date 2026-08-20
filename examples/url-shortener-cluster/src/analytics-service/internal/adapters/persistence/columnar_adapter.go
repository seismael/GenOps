package persistence

import (
	"context"
	"sync"
	"time"

	"analytics-service/internal/domain"
)

// InMemColumnarClickHouseMock simulates ClickHouse vectorized columnar aggregations.
type InMemColumnarClickHouseMock struct {
	mu      sync.RWMutex
	records []domain.ClickRecord
}

func NewInMemColumnarClickHouse() *InMemColumnarClickHouseMock {
	return &InMemColumnarClickHouseMock{
		records: make([]domain.ClickRecord, 0),
	}
}

func (c *InMemColumnarClickHouseMock) InsertBatch(ctx context.Context, records []domain.ClickRecord) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.records = append(c.records, records...)
	return nil
}

func (c *InMemColumnarClickHouseMock) ExecuteAggregation(ctx context.Context, query domain.MetricQuery) (*domain.AnalyticsReport, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	start := time.Now()
	totalClicks := int64(0)
	visitors := make(map[string]bool)
	referrers := make(map[string]int64)
	countries := make(map[string]int64)

	for _, rec := range c.records {
		if rec.Code == query.Code {
			totalClicks++
			visitors[rec.IPAddress] = true
			if rec.Referrer != "" {
				referrers[rec.Referrer]++
			}
			if rec.CountryCode != "" {
				countries[rec.CountryCode]++
			}
		}
	}

	latency := float64(time.Since(start).Microseconds()) / 1000.0

	return &domain.AnalyticsReport{
		Code:             query.Code,
		TenantID:         query.TenantID,
		TotalClicks:      totalClicks,
		UniqueVisitors:   int64(len(visitors)),
		TopReferrers:     referrers,
		CountryBreakdown: countries,
		QueryLatencyMs:   latency,
	}, nil
}
