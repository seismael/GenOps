---
id: LLD-001-ratelimit
domain: ratelimit
stage: lld
version: 1.0.0
status: approved
upstream_refs: [HLD-001-ratelimit, ADR-001-token-bucket-sqlite]
downstream_refs: []
---

# LLD-001: Rate-Limit Engine Design

### Modules
| Module | Scaffold | Entities | Description |
|---|---|---|---|
| `ratelimit-engine` | `python-fastapi` | `RatePolicy, QuotaBucket` | Edge token-bucket quota evaluation & policy store |

## Database Schema
```sql
CREATE TABLE IF NOT EXISTS rate_policies (
    tenant_id TEXT PRIMARY KEY,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    refill_per_sec REAL NOT NULL CHECK (refill_per_sec > 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_buckets (
    tenant_id TEXT PRIMARY KEY,
    tokens REAL NOT NULL,
    last_refill_ms INTEGER NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES rate_policies(tenant_id)
);
```
