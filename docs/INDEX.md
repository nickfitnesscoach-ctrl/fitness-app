# EatFit24 Documentation Index

Welcome to the Single Source of Truth (SSOT) repository for the EatFit24 project. We maintain a strict limit of 11-12 core active documents to prevent fragmentation and "double truth".

---

## 📂 Core Pack (SSOTs)

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Project entry point & high-level mission. |
| [CLAUDE.md](../CLAUDE.md) | AI bootstrap, development rules, and service map. |
| [INDEX.md](INDEX.md) | **You are here.** Central map of all documentation. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System vision, component interaction, and data flows. |
| [ENV.md](ENV.md) | Configuration contract, .env logic, and security levels. |
| [DEPLOY.md](DEPLOY.md) | Quick start, production release steps, and disaster recovery. |
| [SECURITY.md](SECURITY.md) | Secret management, firewall rules, and audit history. |
| [BILLING.md](BILLING.md) | Payments, subscriptions, webhooks, and auto-renew. |
| [AI_PROXY.md](AI_PROXY.md) | AI recognition, image normalization, and LLM contracts. |
| [BOOT_AND_RUNTIME.md](../backend/docs/BOOT_AND_RUNTIME.md) | Server startup, process management, and health checks. |
| [ROOT_FILES_MAP.md](../backend/docs/ROOT_FILES_MAP.md) | Deep-dive file inventory and purpose of root directories. |

---

## 📦 Archive & Research
Historical records, detailed audits, and old guides are preserved for reference but are **NOT** the current source of truth.

- **[docs/archive/](archive/)**: Contains 50+ historical documents.

---

## 🛠 Near-Code READMEs
Some modules contain local READMEs for quick context. They should always link back to the central SSOTs above.

- [backend/apps/billing/docs/](../backend/apps/billing/docs/README.md) -> [docs/BILLING.md](BILLING.md)
- [backend/apps/ai_proxy/](../backend/apps/ai_proxy/README.md) -> [docs/AI_PROXY.md](AI_PROXY.md)

---

## ⚖ Documentation Rules
1. **Rule of 12**: Active documentation should not exceed 12 core files.
2. **SSOT Primacy**: Information must exist in only one place.
3. **Archive or Perish**: If a document is no longer accurate, move it to `/archive` immediately.
