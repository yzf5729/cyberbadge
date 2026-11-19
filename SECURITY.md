# Security policy

## Reporting a vulnerability

Open a private advisory via GitHub: **Security → Advisories → New draft security advisory**,
or email the maintainer listed in `AUTHORS`.

Please include: affected version/commit, steps to reproduce, and impact.

## Scope

- Remote code execution or sandbox escape in the agent tools.
- Path traversal outside `AGENT_WORKDIR`.
- Token/key leakage in logs or the PWA.
- Gateway authentication bypass.

## Not in scope

- Issues that require an already-compromised device.
- Missing hardening on unsupported hardware.

## Practices

- Never commit `.env`, API keys, or device tokens.
- Use scoped credentials and revoke them when devices are retired.
- File tools are sandboxed to `AGENT_WORKDIR`; keep it that way.
