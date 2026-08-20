package streaming

import (
	"context"
	"sync/atomic"

	"redirect-service/internal/domain"
)

// AsyncKafkaProducerMock implements non-blocking high-throughput Kafka streaming.
type AsyncKafkaProducerMock struct {
	eventBuffer chan domain.ClickTelemetry
	count       atomic.Int64
}

func NewAsyncKafkaProducer(bufferSize int) *AsyncKafkaProducerMock {
	p := &AsyncKafkaProducerMock{
		eventBuffer: make(chan domain.ClickTelemetry, bufferSize),
	}
	// Background consumer simulation
	go func() {
		for range p.eventBuffer {
			p.count.Add(1)
		}
	}()
	return p
}

func (k *AsyncKafkaProducerMock) ProduceClickEvent(ctx context.Context, event domain.ClickTelemetry) error {
	select {
	case k.eventBuffer <- event:
		return nil
	default:
		// Ring buffer drop-oldest / non-blocking fallback under extreme surge
		return nil
	}
}

func (k *AsyncKafkaProducerMock) GetProducedCount() int64 {
	return k.count.Load()
}
