# Repository Cleanup - Remove Historical Documentation

**Goal:** Simplify repository to be a clean, actively maintained infrastructure stack with minimal documentation overhead

**Date:** 2026-02-03

## Rationale

This repository serves as a personal, actively maintained home server stack. Historical planning documents, archived guides, and ticket tracking systems add overhead without value for day-to-day operations. All essential operational knowledge is already consolidated in CLAUDE.md.

## Changes

### Directories to Delete

1. **docs/archive/** - 18 archived documentation files
   - All content superseded by CLAUDE.md or no longer relevant

2. **docs/plans/** - 3 implementation plan files
   - Historical planning artifacts not needed for operations

3. **tickets/** - 55+ ticket files across 4 subdirectories
   - security-tickets/
   - monitoring-tickets/
   - dashboard-tickets/
   - domain-access-tickets/
   - All planning artifacts, not operational documentation

### Files to Delete

1. **CONTRIBUTING.md** - Contributor guidelines not needed for personal stack
2. **TESTING-MIDDLEWARE.md** - Obsolete testing notes with hardcoded domain
3. **SECURITY.md** - Historical security implementation documentation

### Files to Move

1. **docs/ARCHITECTURE.md → ARCHITECTURE.md** - Move to root (only file remaining in docs/)
2. Delete empty **docs/** directory after move

### References to Update

**README.md:**
- Update `docs/ARCHITECTURE.md` references to `ARCHITECTURE.md`
- Remove Documentation section (lines 79-110) pointing to archived docs
- Add minimal documentation section referencing CLAUDE.md and ARCHITECTURE.md

**CLAUDE.md:**
- Update `docs/ARCHITECTURE.md` reference to `ARCHITECTURE.md` (line 104)
- Remove all `docs/archive/` references (8 occurrences)

## Final Structure

Root-level documentation only:
```
ARCHITECTURE.md       (visual diagrams)
CLAUDE.md            (primary operational guide)
README.md            (quick start guide)
SERVICES.md          (service catalog)
```

## Impact

**Benefits:**
- Single source of truth for operations (CLAUDE.md)
- No confusion about current vs archived documentation
- Easier to maintain (fewer files to keep in sync)
- Clean repository focused on active infrastructure

**Trade-offs:**
- Loss of historical context about implementation decisions
- No contributor guidelines (acceptable for personal stack)
- No standalone detailed guides (all consolidated in CLAUDE.md)
