package ports

import (
	"context"

	"analytics-service/internal/domain"
)

// IClickHouseAdapter defines the columnar OLAP database port.
type IClickHouseAdapter interface {
	InsertBatch(ctx context.Context, records []domain.ClickRecord) error
	ExecuteAggregation(ctx context.Context, query domain.MetricQuery) (*domain.AnalyticsReport, error)
}
