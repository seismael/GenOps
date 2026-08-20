package services

import (
	"context"

	"analytics-service/internal/domain"
	"analytics-service/internal/ports"
)

type AnalyticsService struct {
	olapAdapter ports.IClickHouseAdapter
}

func NewAnalyticsService(olap ports.IClickHouseAdapter) *AnalyticsService {
	return &AnalyticsService{
		olapAdapter: olap,
	}
}

func (s *AnalyticsService) IngestBatch(ctx context.Context, records []domain.ClickRecord) error {
	return s.olapAdapter.InsertBatch(ctx, records)
}

func (s *AnalyticsService) QueryCampaignAnalytics(ctx context.Context, query domain.MetricQuery) (*domain.AnalyticsReport, error) {
	return s.olapAdapter.ExecuteAggregation(ctx, query)
}
