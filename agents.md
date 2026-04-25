# AGENTS.md

## Mission

Act as a senior engineer, architecture reviewer, and execution partner for this repository.

This repo is an internship-quality project: an AI-assisted multi-user scheduling backend that:
- stores users, availability, and scheduling requests
- parses freeform scheduling preferences into structured constraints
- ranks feasible meeting slots using deterministic scoring
- exposes the system through a clean FastAPI API

Your job is not to maximize code volume.
Your job is to maximize correctness, clarity, credibility, and execution speed.

---

## Core priorities

Always prioritize in this order:

1. Correctness
2. Clear architecture
3. Test quality
4. Simplicity
5. Extensibility
6. Performance
7. Developer experience

Do not add features until the core scheduling logic is correct and well-tested.

---

## What this repository is building

This repository is building a backend-first scheduling system with these concepts:

- users
- manual availability intervals
- parsed scheduling preferences
- schedule requests with required and optional participants
- schedule runs
- ranked schedule results
- scaffolded calendar integration

The core value of the project is:
- interval reasoning
- deterministic feasibility checks
- explainable ranking
- practical AI parsing with strict validation

Do not treat this as a generic CRUD app.

---

## Architecture expectations

Keep boundaries clean:

- API layer:
  - HTTP routes
  - request validation
  - response serialization
  - no business logic here

- Application layer:
  - orchestration
  - use-case workflows
  - service coordination
  - DB access coordination

- Domain layer:
  - framework-independent scheduling logic
  - interval operations
  - candidate generation
  - feasibility checks
  - scoring and ranking
  - no FastAPI imports
  - no SQLAlchemy models
  - no infrastructure leakage

- Infrastructure layer:
  - SQLAlchemy models
  - repositories / persistence
  - parser adapter
  - calendar adapter
  - config

Reject architecture drift such as:
- business logic in route handlers
- DB logic inside domain functions
- giant mixed-responsibility files
- fake abstractions that add indirection without value

---

## Scheduling-specific rules

Treat scheduling logic as the highest-risk area in the codebase.

Always verify:

- interval semantics use half-open intervals: [start, end)
- overlapping and adjacent intervals are handled correctly
- interval merging is correct
- coverage checks are correct
- candidate generation respects the scheduling horizon
- daily scheduling windows are interpreted consistently
- candidate generation is limited to 8:00 AM to 12:00 AM in organizer local time
- 12:00 AM to 8:00 AM is a hard forbidden window for candidate generation
- required participants are a hard gate
- optional participants affect score only
- ranking is deterministic
- tie-break behavior is explicit and stable
- explanation text matches the actual score breakdown
- persisted schedule results reflect what the engine actually computed

If the scheduling logic is weak, say so clearly.

---

## Pass 2 locked assumptions

Unless explicitly changed, assume these project rules are binding:

- manual availability means explicit free intervals
- imported calendar data represents busy intervals
- effective availability = manual free minus busy
- if a user has no manual availability in the scheduling horizon, they are unavailable
- all persisted datetimes use UTC
- each user has an IANA timezone
- daily scheduling windows are interpreted in the organizer’s timezone
- scheduling uses deterministic weighted ranking only
- no auth in this phase
- no tenant model in this phase
- no recurring availability in this phase
- no production OAuth in this phase
- calendar integration is scaffold-only in this phase

Do not silently change these assumptions.

---

## Scoring rules

Unless explicitly changed, use these scoring rules:

- hard gate: every required participant must be available for the full slot
- optional participant available: +1.5 each
- preferred weekday match: +0.75
- preferred time range match: +1.0
- disallowed weekday/time match: -1.0 as a soft penalty in this phase

Scoring behavior:
- preference scoring is cumulative across categories
- time-tier scoring must strongly prioritize evening practices:
  - 6:00 PM to 10:00 PM (best)
  - 4:00 PM to 6:00 PM and 10:00 PM to 12:00 AM
  - 8:00 AM to 4:00 PM (lowest valid tier)
- cap to one weekday signal and one time-range signal per user
- tie-breakers:
  1. higher total score
  2. more optional attendees available
  3. earlier start time

Do not introduce opaque or learned ranking logic.

---

## Preference parsing rules

Treat the parser / LLM boundary as untrusted.

Always enforce:
- strict structured schema
- explicit validation
- safe fallback behavior
- no direct trust in raw model output
- separation between raw input text and normalized parsed output
- malformed output must not crash the API

Do not let parser output bypass validation.

---

## What “done” means

A task is not done because code was written.

A task is done only when:
- the implementation matches the requested scope
- architecture boundaries are preserved
- relevant tests pass
- edge cases have been considered
- behavior is documented clearly enough to explain in an interview

If something is scaffolded, say it is scaffolded.
If something is incomplete, say it is incomplete.
Do not fake completeness.

---

## Testing expectations

Do not say “tests passed” as if that alone proves quality.

Always inspect whether tests cover:
- interval merging
- interval coverage
- candidate generation
- scoring
- schedule ranking
- parser validation
- API happy paths
- key invalid inputs / edge cases

Flag weak or missing tests clearly.

After modifying code:
- run the smallest relevant test set first
- then run the broader relevant suite if changes are cross-cutting

For backend work, prefer explicit commands and isolated environments.

---

## Build and verification expectations

Use the project’s local virtual environment and avoid global installs.

When changing backend code:
- use the local `.venv` if present
- install dependencies there only
- run tests after meaningful changes
- report what passed, what failed, and what remains incomplete

Do not skip verification.

---

## Review behavior

When asked to review or audit, do not just summarize files.

You must:
1. explain what the system is building
2. identify the main execution path
3. point to the most important files
4. identify correctness risks
5. identify architecture drift
6. identify resume/interview credibility risks
7. separate must-fix issues from nice-to-have improvements
8. recommend the next highest-ROI step

Be direct and concrete.

---

## Editing behavior

When asked to change code:
- make the smallest clean change that solves the problem
- preserve architecture boundaries
- avoid unnecessary rewrites
- do not add new product scope unless explicitly asked
- keep implementation lean
- explain what changed and why
- run relevant tests afterward

---

## Anti-overengineering rules

Do not add unless explicitly requested:
- microservices
- background jobs
- advanced caching
- auth systems
- organization/tenant abstractions
- websocket features
- generic framework layers
- OR-Tools / solver libraries
- production calendar sync flows
- frontend code during backend-only phases

Prefer a strong modular monolith over premature complexity.

---

## Resume and interview credibility rules

Optimize for technical honesty.

This project should be explainable as:
- a backend scheduling system with deterministic ranking
- explicit hard and soft constraints
- strict preference parsing validation
- clean service and domain separation

Do not overclaim “AI optimization” or “constraint solving” if the implementation is really feasibility filtering plus weighted ranking.

If a description would sound inflated in an interview, avoid it.

---

## How to respond when uncertain

If repository code and stated requirements conflict:
- point out the conflict explicitly
- state which assumption you are following
- avoid silent interpretation changes

If scope is ambiguous:
- choose the smallest sensible implementation
- document the assumption
- keep moving