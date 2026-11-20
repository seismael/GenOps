---
id: LLD-002-webhooks
domain: webhooks
stage: lld
version: 1.0.0
status: approved
upstream_refs: [HLD-002-webhooks, ADR-001-token-bucket-sqlite]
downstream_refs: []
---

# LLD-002: Webhook Dispatcher Design

### Modules
| Module | Scaffold | Entities | Description |
|---|---|---|---|
| `webhook-dispatcher` | `python-fastapi` | `WebhookEndpoint, DeliveryAttempt` | HMAC-SHA256 signed webhook fan-out & bounded retries |

## Database Schema
```sql
CREATE TABLE IF NOT EXISTS webhook_endpoints (
    endpoint_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS delivery_attempts (
    attempt_id TEXT PRIMARY KEY,
    endpoint_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    FOREIGN KEY (endpoint_id) REFERENCES webhook_endpoints(endpoint_id)
);
```
