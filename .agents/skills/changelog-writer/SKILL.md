---
name: changelog-writer
description: Write concise architecture-focused milestone changelogs for implementation work. Use when a user asks to document what was delivered, include Mermaid diagrams, present DB schema in tables with clear field roles, and add links to relevant files/endpoints/tests.
---

# Changelog Writer

Write changelogs in the same style as project milestone changelogs under `docs/changelog/`.

## Workflow

1. Read the target plan/spec and implementation files before drafting.
2. Map each delivered behavior to concrete code links.
3. Draft a concise changelog using the template in `references/changelog-template.md`.
4. Verify every major claim has at least one file link.

## Output Rules

- Keep writing concise and technical; prefer bullets over long paragraphs.
- Use Markdown links to concrete repo-relative paths for routes, services, models, migrations, tests, and plans.
- Prefer repo-relative links by default; GitHub links are acceptable when a hosted deep link is more useful.
- Never use machine-specific absolute filesystem paths such as `/path/to/repo/...`.
- Include at least one Mermaid diagram (`flowchart` or `sequenceDiagram`) that reflects the real implementation.
- Add a schema section with Markdown tables. Each table row must explain field purpose, not only type.
- Call out key tradeoffs and limits without repeating obvious code details.
- Avoid invented behavior; only document what is implemented.

## Minimum Sections

1. Title + short intro linking the milestone plan/spec.
2. Scope Delivered.
3. Architecture / Flow (Mermaid).
4. Design Notes (major decisions and rationale).
5. Schema Reference (table format with clear explanations).
6. Verification Notes (tests or checks).

## Link Quality

- Prefer deep links to the most specific file that proves the point.
- When useful, include multiple links per bullet (API + core + persistence + test).
- Keep link lists short and relevant.
- Keep every link portable across machines by using repo-relative paths or GitHub URLs only.

## Reusable Template

Use `references/changelog-template.md` as the starting structure and adapt headings to the milestone.
