package domain

import (
	"errors"
	"net"
	"net/url"
	"regexp"
	"time"
)

var (
	ErrInvalidCode      = errors.New("invalid short code format; must be 3-30 alphanumeric characters")
	ErrProhibitedTarget = errors.New("prohibited target URL; loopback and private networks are blocked")
	ErrRouteNotFound    = errors.New("redirect route not found or inactive")
	codeRegex           = regexp.MustCompile(`^[a-zA-Z0-9_-]{3,30}$`)
)

// RedirectRoute represents an enterprise short URL route.
type RedirectRoute struct {
	Code      string
	TargetURL string
	TenantID  string
	IsActive  bool
	CreatedAt time.Time
}

// Validate ensures enterprise routing invariants are satisfied.
func (r *RedirectRoute) Validate() error {
	if !codeRegex.MatchString(r.Code) {
		return ErrInvalidCode
	}
	parsed, err := url.Parse(r.TargetURL)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
		return ErrProhibitedTarget
	}
	host := parsed.Hostname()
	if host == "localhost" {
		return ErrProhibitedTarget
	}
	// SSRF guard: reject loopback, link-local, and RFC1918 private IP literals
	// (127.0.0.0/8, 169.254.0.0/16, 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12,
	// and IPv6 ::1 / fe80::/10 / fc00::/7).
	if ip := net.ParseIP(host); ip != nil {
		if ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsPrivate() || ip.IsUnspecified() {
			return ErrProhibitedTarget
		}
	}
	return nil
}

// ClickTelemetry captures high-velocity immutable telemetry event.
type ClickTelemetry struct {
	EventID       string `json:"event_id"`
	Code          string `json:"code"`
	TenantID      string `json:"tenant_id"`
	TimestampNano int64  `json:"timestamp_nano"`
	IPAddress     string `json:"ip_address"`
	CountryCode   string `json:"country_code"`
	UserAgent     string `json:"user_agent"`
	Referrer      string `json:"referrer"`
}
