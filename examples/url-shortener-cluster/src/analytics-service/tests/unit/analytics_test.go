package unit_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	"analytics-service/internal/adapters/persistence"
	"analytics-service/internal/domain"
	"analytics-service/internal/services"
)

func TestClickHouseBatchIngestionAndAggregation(t *testing.T) {
	clickhouseMock := persistence.NewInMemColumnarClickHouse()
	svc := services.NewAnalyticsService(clickhouseMock)

	// Ingest 5,000 synthetic click events
	batchSize := 5000
	records := make([]domain.ClickRecord, batchSize)
	for i := 0; i < batchSize; i++ {
		records[i] = domain.ClickRecord{
			EventID:     fmt.Sprintf("evt_%d", i),
			Code:        "cybermonday",
			TenantID:    "enterprise_corp",
			Timestamp:   time.Now().Add(-time.Duration(i) * time.Second),
			IPAddress:   fmt.Sprintf("192.0.2.%d", i%256),
			CountryCode: []string{"US", "DE", "FR", "JP", "GB"}[i%5],
			UserAgent:   "Mozilla/5.0",
			Referrer:    []string{"https://google.com", "https://twitter.com", "https://reddit.com"}[i%3],
		}
	}

	ctx := context.Background()
	if err := svc.IngestBatch(ctx, records); err != nil {
		t.Fatalf("failed to ingest batch: %v", err)
	}

	// Query aggregations
	report, err := svc.QueryCampaignAnalytics(ctx, domain.MetricQuery{
		Code:     "cybermonday",
		TenantID: "enterprise_corp",
	})
	if err != nil {
		t.Fatalf("failed to query analytics: %v", err)
	}

	if report.TotalClicks != int64(batchSize) {
		t.Fatalf("expected %d total clicks, got %d", batchSize, report.TotalClicks)
	}

	if report.UniqueVisitors != 256 {
		t.Fatalf("expected 256 unique visitors, got %d", report.UniqueVisitors)
	}

	t.Logf("OLAP Query completed in %.3fms. Total clicks: %d, Unique Visitors: %d, Countries: %v",
		report.QueryLatencyMs, report.TotalClicks, report.UniqueVisitors, report.CountryBreakdown)
}
