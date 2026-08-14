---
id: RFC-001-contextops-architecture
title: "ContextOps: The Docs-as-Context Framework for Agent-Native Software Engineering"
stage: architecture
status: Accepted
date: 2026-08-14
authors: ["Antigravity Architecture Team"]
tags: [architecture, contextops, specification-pipeline, rfc]
---

# RFC-001: ContextOps Architecture & Specification Pipeline

## 1. Executive Summary

Modern AI coding agents fail predominantly due to **monolithic prompt collapse**, **context pollution**, and **architectural drift**. When an agent is tasked with implementing a large feature end-to-end in a single prompt, it mixes business requirements, system topology, technology trade-offs, database schemas, and implementation details into an unverified, hallucination-prone output.

**GenOps** formalizes the **Docs-as-Context (ContextOps)** paradigm through a cascading, separation-of-concerns (SoC) specification pipeline:

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontFamily': 'Inter, system-ui, sans-serif', 'lineColor': '#64748b', 'primaryTextColor': '#0f172a' }}}%%
flowchart LR
    PRD["<b>PRD</b><br/>Product Requirements"] -->|"Cascades into"| HLD["<b>HLD</b><br/>System Topology"]
    HLD -->|"Cascades into"| ADR["<b>ADR</b><br/>Tech Decisions"]
    ADR -->|"Cascades into"| LLD["<b>LLD</b><br/>Contracts & Schemas"]
    LLD -->|"Scaffolds into"| CODE["<b>Code</b><br/>Deterministic Source"]

    classDef stageBox fill:#f8fafc,stroke:#2563eb,stroke-width:1.5px,color:#0f172a,rx:6px,ry:6px;
    class PRD,HLD,ADR,LLD,CODE stageBox;
```

Each stage is isolated in scope, produces machine-readable artifacts with YAML frontmatter, and detects upstream changes via LF-normalized SHA-256 hash tracking:

$$\text{State}(\text{Stage}_i) = f\left(\text{Hash}_{\text{LF}}(\text{Requires}(\text{Stage}_i)), \text{Approved}(\text{Stage}_{i-1})\right)$$

---

## 2. The 6 Pillars of ContextOps

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontFamily': 'Inter, system-ui, sans-serif', 'lineColor': '#64748b', 'primaryTextColor': '#0f172a' }}}%%
flowchart TB
    subgraph Pillars ["The 6 Pillars of the ContextOps Paradigm"]
        direction TB
        P1["1. Strict Downward Traceability (PRD → Code)"]
        P2["2. Token Efficiency via Domain-Split Files"]
        P3["3. Deterministic Machine Indexing (YAML Frontmatter)"]
        P4["4. Anti-Drift Enforcement (LF-Hash & CI Gates)"]
        P5["5. Automated Pass/Fail Verification Loops"]
        P6["6. Multi-Stack Scaffolding Determinism"]
    end

    classDef pBox fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764,rx:6px,ry:6px;
    class P1,P2,P3,P4,P5,P6 pBox;
```

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

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontFamily': 'Inter, system-ui, sans-serif', 'lineColor': '#64748b', 'primaryTextColor': '#0f172a' }}}%%
flowchart LR
    subgraph Tier1 ["Tier 1: Full Enterprise Stack"]
        direction TB
        T1_PRD["PRD"] --> T1_HLD["HLD"] --> T1_ADR["ADR"] --> T1_LLD["LLD"] --> T1_CODE["Code"]
    end

    subgraph Tier2 ["Tier 2: Standard Service"]
        direction TB
        T2_HLD["HLD"] --> T2_ADR["ADR"] --> T2_CODE["Code"]
    end

    subgraph Tier3 ["Tier 3: Light Tool / Prototype"]
        direction TB
        T3_README["README"] --> T3_ADR["ADR"] --> T3_CODE["Code"]
    end

    classDef t1 fill:#f8fafc,stroke:#2563eb,stroke-width:1.5px,color:#0f172a,rx:6px,ry:6px;
    classDef t2 fill:#f8fafc,stroke:#0284c7,stroke-width:1.5px,color:#0f172a,rx:6px,ry:6px;
    classDef t3 fill:#faf5ff,stroke:#9333ea,stroke-width:1.5px,color:#3b0764,rx:6px,ry:6px;
    class T1_PRD,T1_HLD,T1_ADR,T1_LLD,T1_CODE t1;
    class T2_HLD,T2_ADR,T2_CODE t2;
    class T3_README,T3_ADR,T3_CODE t3;
```

---

## 4. Core Non-Negotiables for Agent Workflows

1. **Machine-Readable Metadata (YAML Frontmatter):** Every specification document must include standardized headers (`id`, `domain`, `layer`, `upstream_refs`, `downstream_refs`, `version`).
2. **ADR-First Technical Decisions:** No architecture or dependency overhaul may proceed without an accepted Architecture Decision Record.
3. **Domain-Split Modular Files:** Specifications must remain domain-scoped (`{STAGE}-{NNN}-{slug}.md`) rather than collapsing into monolithic documents.
4. **Deterministic Hash Tracking:** State transitions must be tracked via LF-normalized SHA-256 hashes to guarantee cross-platform determinism across Windows, macOS, and Linux.
