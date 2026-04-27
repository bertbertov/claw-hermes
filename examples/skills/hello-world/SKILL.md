---
name: hello-world
description: Minimal valid dual-runtime skill that prints a greeting in either Hermes or OpenClaw. Use when verifying a freshly-installed claw-hermes setup or when demonstrating the agentskills.io v1.0 runtimes extension to a contributor.
version: 0.1.0
license: MIT
author: claw-hermes contributors
agentskills_version: "1.0"
runtimes:
  hermes:
    entrypoint: python -c "print('hello from hermes')"
    capabilities: []
  openclaw:
    entrypoint: node -e "console.log('hello from openclaw')"
    capabilities: []
  both:
    requires_capabilities: []
keywords: [example, hello-world, dual-runtime]
homepage: https://github.com/bertbertov/claw-hermes
---

# hello-world

The smallest possible dual-runtime skill. Each runtime entrypoint prints a single line and exits.
This file is intentionally short on prose because its purpose is to demonstrate the **shape** of a
valid manifest, not to ship behavior. Use it as a template when you start a new skill, or feed it
to `claw-hermes skill lint` as a sanity check that your local installation parses the v1.0
manifest schema correctly.

## When to invoke this skill

- "verify my claw-hermes install is wired up"
- "show me a minimal dual-runtime SKILL.md"
- "what's the simplest manifest that lints clean?"

## Inputs and outputs

There are no inputs. Each runtime entrypoint prints a fixed greeting to stdout and exits with
code 0. The skill exists purely to exercise the manifest pipeline end-to-end without invoking
any external services or capabilities.
