# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through [GitHub security advisories](https://github.com/Venorium/PrincipalLoop/security/advisories/new). Do not open a public issue for a suspected vulnerability. You should receive an answer within a week.

Useful reports include the version (`principalloop --version`), the operating system, the steps to reproduce and the impact you observed.

## What PrincipalLoop protects, and what it does not

PrincipalLoop runs locally, makes no network request and calls no model. Its security boundaries are deliberately narrow:

- **In scope.** A tool call that selects a workspace, a role or a file outside the human's list; a path that escapes the project root (`..`, links, junctions, hard links); captured content being treated as instructions; private state written inside a repository or a known synchronized folder; an error reported as `UNCHANGED`; report HTML executing injected content.
- **Out of scope by design.** The integration is **COOPERATIVE**: an agent or process running under the same operating system account can read or modify the private state directly. PrincipalLoop does not sandbox Codex's own tools and does not protect against a local administrator.

Checkpoints may contain whatever you chose to track. Treat generated reports (`principalloop codex report`) as private files.
