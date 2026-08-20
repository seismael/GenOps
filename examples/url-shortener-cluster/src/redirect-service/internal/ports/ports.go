package ports

import (
	"context"
	"time"

	"redirect-service/internal/domain"
)

// IRedisCachePort defines the interface for distributed Redis Cluster lookups.
type IRedisCachePort interface {
	Get(ctx context.Context, code string) (string, error)
	Set(ctx context.Context, code string, targetURL string, ttl time.Duration) error
}

// IKafkaProducerPort defines the non-blocking streaming producer interface.
type IKafkaProducerPort interface {
	ProduceClickEvent(ctx context.Context, event domain.ClickTelemetry) error
	GetProducedCount() int64
}
