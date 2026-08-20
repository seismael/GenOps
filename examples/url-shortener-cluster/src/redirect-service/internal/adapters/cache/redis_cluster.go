package cache

import (
	"context"
	"sync"
	"time"
)

// MemoryRedisClusterMock provides a thread-safe, high-concurrency simulation of the
// Redis Cluster L1/L2 cache tier described in ADR-001-distributed-storage-stack.md.
// In production this adapter would speak the Redis Cluster protocol; this in-memory
// mock keeps the example self-contained (see RedirectService.routes for the
// asynchronous PostgreSQL fallback that stands in for the cache-miss path).
type MemoryRedisClusterMock struct {
	mu    sync.RWMutex
	store map[string]string
}

func NewMemoryRedisCluster() *MemoryRedisClusterMock {
	return &MemoryRedisClusterMock{
		store: make(map[string]string),
	}
}

func (r *MemoryRedisClusterMock) Get(ctx context.Context, code string) (string, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	val, exists := r.store[code]
	if !exists {
		return "", nil
	}
	return val, nil
}

func (r *MemoryRedisClusterMock) Set(ctx context.Context, code string, targetURL string, ttl time.Duration) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.store[code] = targetURL
	return nil
}
