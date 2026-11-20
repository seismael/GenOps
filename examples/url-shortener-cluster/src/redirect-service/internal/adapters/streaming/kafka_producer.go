package streaming

import (
	"context"
	"sync"
	"sync/atomic"

	"redirect-service/internal/domain"
)

// AsyncKafkaProducerMock implements non-blocking high-throughput Kafka streaming.
type AsyncKafkaProducerMock struct {
	eventBuffer chan domain.ClickTelemetry
	count       atomic.Int64
	closeOnce   sync.Once
	wg          sync.WaitGroup
}

func NewAsyncKafkaProducer(bufferSize int) *AsyncKafkaProducerMock {
	p := &AsyncKafkaProducerMock{
		eventBuffer: make(chan domain.ClickTelemetry, bufferSize),
	}
	p.wg.Add(1)
	// Background consumer simulation
	go func() {
		defer p.wg.Done()
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
		// Non-blocking drop-newest load shedding when producer buffer is saturated
		return nil
	}
}

func (k *AsyncKafkaProducerMock) GetProducedCount() int64 {
	return k.count.Load()
}

// Close shuts down the background consumer goroutine cleanly after draining buffered events.
func (k *AsyncKafkaProducerMock) Close() {
	k.closeOnce.Do(func() {
		close(k.eventBuffer)
		k.wg.Wait()
	})
}
