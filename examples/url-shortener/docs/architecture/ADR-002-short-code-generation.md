---
id: ADR-002-short-code-generation
domain: algorithm
stage: adr
version: 1.0.0
status: accepted
upstream_refs: ["HLD-001-url-shortener"]
downstream_refs: ["LLD-001-url-shortener"]
tags: [adr, architecture, algorithm, base62, encoding]
---

# ADR-002: Base62 Cryptographic Hash Truncation for Short-Code Generation

## 1. Context & Problem Statement
The service needs to generate compact, URL-safe short codes (e.g. `k7X9qZb`) from arbitrary target URLs. The generation mechanism must guarantee high entropy, zero sequential predictability (preventing malicious attackers from enumerating all short links via integer incrementing), exactly 0 collisions, and a fixed length of 7 alphanumeric characters ($62^7 \approx 3.52 \times 10^{12}$ unique URLs).

## 2. Decision Candidates Evaluated
- **Option A (Accepted):** SHA-256 + Nanosecond Salt truncated and encoded to 7-character Base62 string (`[0-9a-zA-Z]`).
- **Option B:** Auto-Incrementing Integer ID encoded to Base62.
- **Option C:** Random UUIDv4 / UUIDv7 formatted string.

## 3. Weighted Multi-Criteria Decision Matrix
*Scale: 1 (Poor) to 5 (Excellent). Weights sum to 100%.*

| Evaluation Vector | Weight | Option A: Base62 Hash | Option B: Auto-Inc Base62 | Option C: UUID String |
|---|---|---|---|---|
| **URL Compactness (≤ 7 chars)** | 30% | **5** (7 chars) | 5 (1-6 chars) | 1 (36 chars) |
| **Security & Non-Enumerability** | 30% | **5** (Non-predictable) | 1 (Easily scraped) | 5 (Cryptographic) |
| **Collision Resilience** | 20% | **5** (3.5 Trillion space) | 5 (Unique ID) | 5 (Unique ID) |
| **Zero Coordination Overhead** | 20% | **5** (Stateless compute) | 2 (Requires DB lock) | 5 (Stateless compute) |
| **Weighted Total** | **100%** | **5.00 / 5.00** | 2.90 / 5.00 | 3.80 / 5.00 |

## 4. Decision Outcome & Rationale
**Selected Option A (Base62 Cryptographic Hash Truncation).**  
It provides 7-character compact URLs without exposing sequential counters or requiring centralized coordination tokens across distributed worker nodes.

## 5. Consequences & Reversibility Strategy
- **Collision Handling:** If a generated 7-character code already exists with a different target URL, the generator re-hashes with an incremented salt index.
- **Reversibility:** The short code generator is encapsulated in a pure domain utility (`Base62Encoder` / `ShortCodeGenerator`).

## 6. Downstream Directives for LLD & Code
1. Short code alphabet MUST be strictly `0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ`.
2. Default code length MUST be exactly 7 characters.
3. Custom aliases provided by users MUST validate against regex `^[a-zA-Z0-9_-]{3,30}$`.
