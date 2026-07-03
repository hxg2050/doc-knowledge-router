# Contributing

This repository keeps two audiences separate:

- Root-level files are for humans: install docs, examples, changelog, license, and contribution rules.
- `skills/<skill-name>/` folders are for agents: concise instructions and bundled resources only.

## Add or Update a Skill

1. Put the skill in `skills/<skill-name>/`.
2. Keep the folder name equal to the `name:` field in `SKILL.md`.
3. Write `SKILL.md` frontmatter with only `name` and `description`.
4. Keep detailed reference material in `references/` instead of bloating `SKILL.md`.
5. Put deterministic helpers in `scripts/` inside the skill folder when repeated execution matters.
6. Put templates, images, or reusable assets in `assets/`.
7. Add or update `agents/openai.yaml`.
8. Add or update the entry in `skills/llms.txt`.
9. Add a realistic example under `examples/`.
10. Run validation before opening a PR.

```bash
node scripts/validate-skills.mjs
```

## Skill Folder Rules

Do not place human-facing documentation inside a skill folder. Avoid:

- `README.md`
- `INSTALL.md`
- `QUICKSTART.md`
- `CHANGELOG.md`

Those files belong at the repository root or in `examples/`.

## Versioning

If a skill has users who depend on its exact behavior, preserve the old behavior under a versioned install name such as `my-skill-v1` before making a breaking rewrite.
