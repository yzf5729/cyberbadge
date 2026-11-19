# Product definition v0.1 (draft)

## One-liner

**CyberBadge is a pocket butler for all your personal devices**: an always-on AI agent that carries your identity and permissions and orchestrates the PCs, NAS, routers and gateways you own at home, in the office and in the cloud.

## What it is

- A **pocket** agent host (badge form factor), online 24/7.
- A **unified control plane** for heterogeneous personal devices.
- A **trusted executor**: it acts with your identity, but every step can be authorized, audited and revoked.

## What it is not

- Not remote desktop (it moves tasks, not pixels).
- Not another smart-home app (it manages devices that *do work*, not just lights).
- Not a master key that sprays root passwords everywhere.

## Three layers

```
┌─ Identity & permissions ─────────────────────┐
│ device keys (secure enclave) / tiered auth /  │
│ second confirmation / audit log               │
└───────────────────────────────────────────────┘
┌─ Connectivity ────────────────────────────────┐
│ overlay network (Tailscale/WireGuard) +       │
│ per-device connectors                         │
└───────────────────────────────────────────────┘
┌─ Execution ───────────────────────────────────┐
│ agent tools: SSH / HTTP API / files /         │
│ services / logs                               │
└───────────────────────────────────────────────┘
```

## Permission model (the key part)

"Highest privilege" does not mean "root by default".

| Tier | Capability | Default |
|---|---|---|
| L0 read-only | status, logs, file listing, capacity | allowed |
| L1 low-risk write | start tasks, download files, restart services | confirm each time |
| L2 high-risk | edit config, delete data, shutdown, change network | second confirmation + audit |
| L3 root | system-level operations, key rotation | allow-listed devices + strong confirmation |

Every action is logged (who, when, which device, what, result).

## Device onboarding

| Device | How |
|---|---|
| Linux / macOS | SSH (keys) or a lightweight connector |
| Windows | OpenSSH + PowerShell connector (read-only tier first) |
| NAS (Synology/QNAP) | official API, SSH as fallback |
| Router / gateway | SSH / HTTP API (OpenWrt, etc.) |
| Cloud VMs | SSH + cloud API |
| Smart home | bridged via Home Assistant, not direct |

## MVP scope (three actions + four device classes)

1. **See**: online status, disk, load, service health.
2. **Files**: upload/download in authorized directories.
3. **One command**: allow-listed command + confirmation + output.

| Device | v1 support | Notes |
|---|---|---|
| Linux / macOS | full (L0–L2) | SSH, same protocol family |
| **Windows** | **L0 + files** | via OpenSSH; no elevation, no GUI automation |
| NAS | L0 + files | official API first, SSH fallback |
| Router / gateway | L0 + restart/network (L2) | SSH/HTTP |

Windows note: it is the most valuable office target but the messiest to onboard — SSH is often off, admin work needs UAC, service control and GUI automation are limited by session isolation. So v1 ships **non-elevated reads and files**; L2 comes once the connector matures.

Plus: **audit log** and **remote revocation** (one click to kick a lost device).

## Relation to existing tools

- **Tailscale/WireGuard**: makes devices reachable; we make them *do things*.
- **Home Assistant**: home automation; we target device operations and files.
- **Ansible/scripts**: batch execution; we add "one sentence → approval → explanation".
- **MCP servers**: reusable as part of the execution layer.

## Risks

| Risk | Mitigation |
|---|---|
| Lost device = lost keys | secure element + remote revocation + short-lived tokens |
| Over-privilege | tiering + second confirmation + allow-lists |
| Heterogeneous devices | pluggable connectors; start with 4 classes |
| Unreachable networks | overlay network; reverse connections when needed |
| Office compliance | read-only default, audit trail, kill switch |
| Single point of failure | run tasks on the target, the badge only orchestrates |

## Success metrics

- Steps from intent to done (target ≤ 2).
- Onboarding time per device (target ≤ 10 min).
- Audit coverage (target 100%).
- Error rate and mean time to recover.
