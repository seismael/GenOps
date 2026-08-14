---
id: RFC-001-contextops-architecture
title: "ContextOps: The Docs-as-Context Framework for Agent-Native Software Engineering"
status: Accepted
date: 2026-08-14
authors: ["Antigravity Architecture Team"]
tags: [architecture, contextops, specification-pipeline, rfc]
---

# RFC-001: ContextOps Architecture & Specification Pipeline

## 1. Executive Summary

Modern AI coding agents fail predominantly due to **monolithic prompt collapse**, **context pollution**, and **architectural drift**. When an agent is tasked with implementing a large feature end-to-end in a single prompt, it mixes business requirements, system topology, technology trade-offs, database schemas, and implementation details into an unverified, hallucination-prone output.

**GenOps** formalizes the **Docs-as-Context (ContextOps)** paradigm through a cascading, separation-of-concerns (SoC) specification pipeline:

$$\text{PRD} \xrightarrow{\text{cascade}} \text{HLD} \xrightarrow{\text{cascade}} \text{ADR} \xrightarrow{\text{cascade}} \text{LLD} \xrightarrow{\text{cascade}} \text{Code}$$

Each stage is isolated in scope, produces machine-readable artifacts with YAML frontmatter, and detects upstream changes via LF-normalized SHA-256 hash tracking.

---

## 2. The 6 Pillars of ContextOps

| Pillar | Mechanism | Value for Humans & AI Agents |
|---|---|---|
| **1. Strict Traceability** | $PRD \rightarrow HLD \rightarrow ADR \rightarrow LLD \rightarrow Code$ | Establishes a downward dependency chain ensuring every line of code traces directly to verified business intent. |
| **2. Token Efficiency** | Single-responsibility domain-split files | Prevents context window saturation. Agents load only the specific $4096\text{-byte}$ aligned LLD or ADR relevant to their current task. |
| **3. Machine Indexing** | Standard YAML Frontmatter + JSON Schemas | Replaces fuzzy semantic RAG search with deterministic graph traversal during context retrieval. |
| **4. Anti-Drift Enforcement** | Deterministic LF-normalized hashing & CI gates | Blocks builds when source code changes without accompanying spec updates. |
| **5. Automated Verification** | Pre-flight validation & compiler feedback loops | Replaces subjective agent self-evaluation with concrete pass/fail verification. |
| **6. Scaffolding Determinism** | Tech-stack-aware scaffolds with multi-casing transforms | Generates consistent boilerplate, interfaces, and stubs directly from LLD design. |

---

## 3. The Architecture Scaling Spectrum

Applying the full four-tier stack to every simple script creates unnecessary friction. GenOps scales dynamically across three tiers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ARCHITECTURE DOCUMENTATION SPECTRUM                    │
├─────────────────┬───────────────────────────────┬───────────────────────────┤
│ Tier            │ Cascade Pipeline              │ Recommended Use Cases     │
├─────────────────┼───────────────────────────────┼───────────────────────────┤
│ Tier 1: Full    │ PRD → HLD → ADR → LLD → Code  │ Core infrastructure,      │
│ Stack           │                               │ distributed systems,      │
│                 │                               │ multi-service platforms   │
├─────────────────┼───────────────────────────────┼───────────────────────────┤
│ Tier 2: Standard│ HLD → ADR → Code              │ REST/gRPC microservices,  │
│ Service         │                               │ web backends, ETL jobs    │
├─────────────────┼───────────────────────────────┼───────────────────────────┤
│ Tier 3: Light   │ README → ADR → Code           │ Internal developer tools, │
│ Utility         │                               │ CLI scripts, prototypes   │
└─────────────────┴───────────────────────────────┴───────────────────────────┘
```

---

## 4. Core Non-Negotiables for Agent Workflows

1. **Machine-Readable Metadata (YAML Frontmatter):** Every specification document must include standardized headers (`id`, `domain`, `layer`, `upstream_refs`, `downstream_refs`, `version`).
2. **ADR-First Technical Decisions:** No architecture or dependency overhaul may proceed without an accepted Architecture Decision Record.
3. **Domain-Split Modular Files:** Specifications must remain domain-scoped (`{STAGE}-{NNN}-{slug}.md`) rather than collapsing into monolithic documents.
4. **Deterministic Hash Tracking:** State transitions must be tracked via LF-normalized SHA-256 hashes to guarantee cross-platform determinism across Windows, macOS, and Linux.
