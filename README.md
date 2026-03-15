# ⚠️ DEPRECATED — This repository has been archived

**Canonical repository:** [`Eldonlandsupply/openclaw`](https://github.com/Eldonlandsupply/openclaw)  
**All code lives at:** [`Eldonlandsupply/openclaw/eldon/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon)  
**Archived on:** 2026-03-15  

---

## What happened

The `EldonOpenClaw` repository has been consolidated into `Eldonlandsupply/openclaw` as the single
canonical repository for all Eldon Land Supply AI infrastructure.

The entire codebase — Python runtime, action allowlist, gateway, memory system, docs, scripts, and
tests — was moved to the `eldon/` subdirectory of the canonical repo with no data loss.

## Where to find everything

| Was here | Now here |
|---|---|
| `src/openclaw/` | [`eldon/src/openclaw/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/src/openclaw) |
| `action_allowlist/` | [`eldon/action_allowlist/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/action_allowlist) |
| `gateway/` | [`eldon/gateway/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/gateway) |
| `memory-system/` | [`eldon/memory-system/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/memory-system) |
| `docs/` | [`eldon/docs/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/docs) |
| `deploy/` | [`eldon/deploy/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/deploy) |
| `scripts/` | [`eldon/scripts/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/scripts) |
| `tests/` | [`eldon/tests/`](https://github.com/Eldonlandsupply/openclaw/tree/main/eldon/tests) |

## Pi deployment

The Raspberry Pi at `/opt/openclaw` currently points to this repo. Future pulls should use:

```bash
# Update Pi remote to canonical repo
cd /opt/openclaw
git remote set-url origin https://github.com/Eldonlandsupply/openclaw.git
```

Note: the Pi's working tree is rooted at what was the top of `EldonOpenClaw`. After switching
remotes, the Pi path would need to be updated to `/opt/openclaw/eldon/` — coordinate this
migration carefully to avoid breaking the running service.

## Do not open new issues or PRs here

This repo is archived. All development continues in [`Eldonlandsupply/openclaw`](https://github.com/Eldonlandsupply/openclaw).
