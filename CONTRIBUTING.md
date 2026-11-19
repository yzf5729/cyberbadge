# Contributing

Thanks for your interest in CyberBadge!

## Ways to help

- Report bugs via the issue templates.
- Propose devices to support (NAS, routers, Windows).
- Improve docs, translations, and the BOM.
- Send pull requests.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn device.main:app --reload --port 8000
```

CI runs `compileall` plus a small smoke test on Python 3.10 and 3.12.

## Pull requests

- Keep changes focused; one topic per PR.
- Explain *why* in the description.
- No secrets in commits (keys, tokens, .env).
- Follow the existing style; run `python -m compileall -q device gateway` before pushing.

## Security

Please do not open public issues for vulnerabilities — see `SECURITY.md`.
