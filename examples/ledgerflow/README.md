# LedgerFlow Double-Entry Financial Ledger (Multi-Domain GenOps Example)

A multi-domain, end-to-end reference project built through every stage of the **GenOps Software Specification Pipeline** (`genops.yaml` -> `PRD` -> `HLD` -> `ADR` -> `LLD` -> `Code`). It demonstrates clean domain separation between `accounts` (`accounts-service`) and `transactions` (`transactions-service`) sharing two cross-cutting architectural decisions.

## Multi-Domain Pipeline Structure

```text
examples/ledgerflow/
├── genops.yaml                                       # Software Specification preset configuration
├── docs/
│   ├── prd/
│   │   ├── PRD-001-accounts.md                       # Accounts & policy requirements (US-001-01..03)
│   │   └── PRD-002-transactions.md                   # Double-entry, idempotency & reversal (US-002-01..03)
│   ├── hld/
│   │   ├── HLD-001-accounts.md                       # Accounts C4 topology, sequences & Trust Boundaries
│   │   └── HLD-002-transactions.md                   # Transactions C4 topology & CloudEvents contracts
│   ├── architecture/
│   │   ├── ADR-001-sqlite-double-entry-ledger.md     # SQLite WAL + BEGIN IMMEDIATE + integer minor units
│   │   └── ADR-002-cloudevents-audit-stream.md       # CNCF CloudEvents v1.0.2 + RFC 9457 Problem Details
│   └── lld/
│       ├── LLD-001-accounts.md                       # Accounts aggregates, SQL DDL, OpenAPI 3.1 & Module blueprint
│       └── LLD-002-transactions.md                   # Transactions aggregates, SQL DDL, OpenAPI 3.1 & Module blueprint
└── src/
    ├── accounts-service/                             # Accounts hexagonal service (`Account`, `LedgerPolicy`)
    └── transactions-service/                         # Double-entry posting & reversal service (`JournalEntry`, `PostingLine`)
```

## Run GenOps Governance Gates

```powershell
# Consolidated pipeline health & governance gate
python .agents/scripts/genops.py --root examples/ledgerflow doctor

# Live pipeline state & domain-isolated context slicing
python .agents/scripts/genops.py --root examples/ledgerflow status
python .agents/scripts/genops.py --root examples/ledgerflow context --domain accounts
python .agents/scripts/genops.py --root examples/ledgerflow impact PRD-001-accounts
python .agents/scripts/genops.py --root examples/ledgerflow rtm
```

## Run Service Test Suites

Both services execute zero-dependency Python 3.8+ stdlib tests via their hexagonal gateways (and also mount FastAPI routers + RFC 9457 handlers when `fastapi` + `pydantic` + `httpx` are installed):

```powershell
cd examples/ledgerflow/src/accounts-service
python -W default -m unittest discover -s tests -p "test_*.py" -v

cd ../transactions-service
python -W default -m unittest discover -s tests -p "test_*.py" -v
```
