package domain

import "time"

// MetricQuery represents a tenant multi-dimensional OLAP query.
type MetricQuery struct {
	Code      string
	TenantID  string
	StartTime time.Time
	EndTime   time.Time
	GroupBy   string
}

// ClickRecord represents a single flattened telemetry event stored in ClickHouse.
type ClickRecord struct {
	EventID     string    `json:"event_id"`
	Code        string    `json:"code"`
	TenantID    string    `json:"tenant_id"`
	Timestamp   time.Time `json:"timestamp"`
	IPAddress   string    `json:"ip_address"`
	CountryCode string    `json:"country_code"`
	UserAgent   string    `json:"user_agent"`
	Referrer    string    `json:"referrer"`
}

// AnalyticsReport contains the aggregated multi-dimensional telemetry summary.
type AnalyticsReport struct {
	Code             string           `json:"code"`
	TenantID         string           `json:"tenant_id"`
	TotalClicks      int64            `json:"total_clicks"`
	UniqueVisitors   int64            `json:"unique_visitors"`
	TopReferrers     map[string]int64 `json:"top_referrers"`
	CountryBreakdown map[string]int64 `json:"country_breakdown"`
	QueryLatencyMs   float64          `json:"query_latency_ms"`
}
