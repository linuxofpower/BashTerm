# BashTerm

BashTerm is a public collection of Python-powered terminal tools for Linux/Bash and Android/Termux.

The goal is to keep small, useful scripts in one place so they can be reused across a normal Linux machine and Termux without turning every utility into a separate project.

## Scope

BashTerm is intended for:

- Python CLI utilities
- Bash helpers and wrappers
- Termux-specific scripts
- Linux terminal automation
- bootstrap and installation helpers
- reusable command-line experiments that are useful enough to keep

## Design principles

- **Terminal first.** Tools should work naturally from the command line.
- **Portable where practical.** Shared logic should work across Linux and Termux when possible.
- **Small and inspectable.** Prefer understandable scripts over opaque automation.
- **Python for logic, shell for glue.** Use whichever layer makes the task simpler.
- **Safe defaults.** Destructive behavior should be explicit rather than surprising.
- **Public-safe repository.** No credentials, tokens, private keys, personal data, or machine-specific secrets belong here.

## Planned structure

```text
BashTerm/
├── scripts/        # Python and shell utilities
├── termux/         # Termux-specific helpers
├── linux/          # Linux-specific helpers
├── shared/         # reusable cross-platform modules
├── install/        # bootstrap/setup scripts
└── docs/           # usage notes and examples
```

The layout may evolve as the first real tools are added.

## Status

Early initialization. The repository currently serves as the home for upcoming Bash/Termux-oriented Python scripts and terminal utilities.

## Usage

Individual tools will document their own requirements and examples. A common installation/bootstrap path will be added once enough scripts exist to justify one.

## Security

Never commit:

- passwords or recovery codes
- API/access tokens
- private keys
- reusable credentials
- `.env` files containing secrets
- private personal or machine-specific data

---

BashTerm is intentionally lightweight: useful terminal tools first, framework later.
