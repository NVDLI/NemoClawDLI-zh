---
name: skills-manager
description: "Manage agent skills: add, remove, snapshot, restore. Use when the user asks to add/remove/list skills, or when you need to manage your own skill set."
---

# Skills Manager

Skills are auto-discovered from `workspace/skills/*/SKILL.md`. No registration or apply step needed.

## CLI

```bash
bash workspace/bin/skills.sh list              # Show installed skills
bash workspace/bin/skills.sh add <name>        # Scaffold a new skill
bash workspace/bin/skills.sh add <name> --from /path/to/dir  # Import
bash workspace/bin/skills.sh remove <name>     # Move to .skill-trash/
bash workspace/bin/skills.sh snapshot <name>   # Checkpoint all skills
bash workspace/bin/skills.sh restore <name>    # Restore from checkpoint
bash workspace/bin/skills.sh seed <dir>        # Bulk import
```

## Creating Skills

A skill is a directory with a `SKILL.md` file:

```
skills/my-skill/
├── SKILL.md           # Required: frontmatter (name, description) + instructions
├── references/        # Optional: reference docs, templates
└── scripts/           # Optional: helper scripts
```

The skill triggers on its SKILL.md frontmatter `description` field, so write that field with the specific keywords that should match.

## When to Create Skills

Create a skill when you find yourself repeating a multi-step pattern. A skill codifies the pattern so you (or a future session) can execute it reliably.
