# Krypton URL Shortener & Analytics Gateway (GenOps Example Project)

A complete, runnable example built with the **GenOps Software Specification Pipeline** (`PRD → HLD → ADR → LLD → Code`). It demonstrates the full Docs-as-Context flow: every design decision in `docs/` is traceable to an implementation in `src/`.

## Pipeline Artifacts

```
examples/url-shortener/
├── docs/
│   ├── prd/PRD-001-url-shortener.md         # Product Requirements & BDD user stories
│   ├── hld/HLD-001-url-shortener.md         # C4 system topology & data flow
│   ├── architecture/
│   │   ├── ADR-001-storage-engine.md        # Storage decision (SQLite WAL)
│   │   └── ADR-002-short-code-generation.md # Base62 deterministic encoding
│   └── lld/LLD-001-url-shortener.md         # Domain models, SQL DDL & OpenAPI 3.1
└── src/url-shortener/                       # Clean/hexagonal Python implementation
    ├── pyproject.toml                       # FastAPI + Pydantic v2 deps
    ├── app/
    │   ├── container.py                     # Dependency-injection wiring
    │   ├── deps.py                          # FastAPI dependencies (cached container, API-key auth)
    │   ├── main.py                          # create_app(), uvicorn entry point
    │   ├── domain/                          # Pure entities + invariants (ShortUrl, ClickEvent, ApiKey)
    │   ├── ports/repository.py              # Repository interfaces (hexagonal ports)
    │   ├── services/short_url_service.py    # Use-case orchestration + Base62 generator
    │   ├── adapters/persistence/            # SQLite WAL adapter (parameterized SQL)
    │   └── routers/                         # FastAPI routes (shorten, redirect, analytics, api-keys)
    └── tests/unit/                          # 26 unit + integration tests
```

## Run the tests

```powershell
cd examples/url-shortener/src/url-shortener
python -m unittest discover -s tests -p "test_*.py" -v
```

All 26 tests should pass (domain validation, SSRF rejection, API-key auth, and an end-to-end shorten → redirect → analytics lifecycle).

## Run the API

```powershell
cd examples/url-shortener/src/url-shortener
python -m pip install "fastapi>=0.110" "pydantic>=2.6" "uvicorn>=0.27"
uvicorn app.main:app --reload
```

Then exercise the endpoints:

```powershell
# Health check
curl http://127.0.0.1:8000/healthz

# Create an API key (returns a token)
curl -X POST http://127.0.0.1:8000/api/v1/api-keys -H "Content-Type: application/json" -d '{"owner_email":"dev@example.com","raw_token":"my-secret-token"}'

# Shorten a URL (401 without the token, 409 on alias collision, 400 on private/loopback targets)
curl -X POST http://127.0.0.1:8000/api/v1/shorten -H "Content-Type: application/json" -H "X-API-Key: my-secret-token" -d '{"url":"https://example.com/a/very/long/path"}'

# Redirect (302 Location)
curl -i http://127.0.0.1:8000/<code>

# Analytics (200 with total_clicks + recent_referrers)
curl http://127.0.0.1:8000/api/v1/analytics/<code> -H "X-API-Key: my-secret-token"
```

## Notable design qualities

- **SSRF hardening**: the `ShortUrl` domain rejects loopback, RFC1918, link-local, and cloud-metadata (`169.254.169.254`) targets.
- **Parameterized SQL** throughout the SQLite adapter (no injection surface).
- **Deterministic, collision-safe** Base62 short codes with salt retry.
- **Clean architecture**: domain → ports → services → adapters → routers, with an in-memory DI container.
