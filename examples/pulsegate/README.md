# PulseGate Edge Rate-Limiter & Webhook Platform (GenOps v3.2.0 Dogfooding Example)

Built end-to-end as a real user of **GenOps v3.2.0**, exercising:
- **YAML 1.2 Core Frontmatter**: block scalars (`summary: |-`), nested flow mappings (`meta: {...}`), and null keys.
- **Federated Cross-Repo Lineage**: `pipeline.federation.remotes` (`alias: ledger`, `path: "../ledgerflow"`) linking `HLD-002-webhooks` to `ext://ledger/ADR-002-cloudevents-audit-stream`.
- **Stage Explainability & Approval Gates**: `genops explain`, `genops record`, `genops context --domain`, `genops impact`, `genops rtm`, `genops report`, `genops rotate-events`, and `genops doctor --sarif`.
- **AST/SQL Anti-Drift & `.genopsignore`**: Python `ast.parse` symbol verification, SQL `CREATE TABLE` DDL parity, and `.genopsignore` reverse-drift exclusion for `src/ops-tools/`.

## Quick Verification

```powershell
python .agents/scripts/genops.py --root examples/pulsegate doctor
python .agents/scripts/genops.py --root examples/pulsegate doctor --sarif
python .agents/scripts/genops.py --root examples/pulsegate status
python .agents/scripts/genops.py --root examples/pulsegate rtm
python .agents/scripts/genops.py --root examples workspace doctor
```
