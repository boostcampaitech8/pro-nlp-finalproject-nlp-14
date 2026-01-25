# Agent Docs Index

This index lists the docs under `docs/agent` with short summaries and when to read them.

## Quick map

- Need the product vision, roles, and decisions: `./mithub-agent-overview.md`
- Need graph structure and architecture choices: `./mithub-langgraph-architecture.md`
- Need directory structure and step-by-step dev workflow: `./mithub-langgraph-development-guideline.md`
- Need naming and coding rules: `./mithub-langgraph-coding-convention.md`

## Documents

| Document | Summary | Use when | Keywords |
| --- | --- | --- | --- |
| `./mithub-agent-overview.md` | High-level vision, roles, and key decisions for the MitHub agent. | You need product-level context or a quick brief. | vision, roles, decisions |
| `./mithub-langgraph-architecture.md` | Graph structure, subgraph strategy, and state sharing principles. | You are designing or reviewing architecture. | graph, subgraph, principles |
| `./mithub-langgraph-development-guideline.md` | Directory layout, development workflow for adding nodes/subgraphs, and common edit locations. | You are implementing or modifying workflows. | layout, workflow, checklist, edit-guide |
| `./mithub-langgraph-coding-convention.md` | Naming rules and implementation conventions for nodes and graph code. | You are coding and want rule-level guidance. | naming, rules, logging, types |

## Plan Documents

작업 계획 및 구현 가이드 문서

| Document | Summary | Use when |
| --- | --- | --- |
| `./plan/neo4j-docker-setup.md` | Neo4j Docker Compose 설정 및 실행 | Neo4j 인프라 구축 시 |
| `./plan/neo4j-schema-setup.md` | 스키마 정의, 인덱스, CSV import | 데이터베이스 구조 설계 시 |
| `./plan/neo4j-usage-patterns.md` | Python 드라이버, Repository 패턴 | Backend에서 Neo4j 사용 시 |
| `./plan/neo4j-mocking-strategy.md` | 인터페이스 추상화, Mock 구현체 | 실제 구현 전 개발 단계 |
| `./plan/neo4j-sync-strategy.md` | PostgreSQL ↔ Neo4j 동기화 전략 | 데이터 동기화 구현 시 |
