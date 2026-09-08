<p align="center">
  <img src="assets/totebag.png" alt="totebag" width="120" />
</p>

# totebag

**Portable, vendor-neutral project knowledge any AI Agent can restore over a CLI.**

Built by [StratoNext](https://www.stratonext.ai).

Your context shouldn't live inside one vendor's chat history. `totebag` keeps it in a portable
store you address with a single root URL — any agent that can run a shell command restores a
project with one call and writes back what it learns. No server, no API keys, no lock-in.

## Install

```bash
uv tool install totebag
```

## Quickstart

Create a project with a description, add work to it, then dump its context:

```bash
totebag init
PID=$(totebag project create --name "Payments API" --description "Billing service")
totebag project use $PID

totebag task add --title "Wire webhooks" --description "handle Stripe retries"
totebag tool add --name reconcile --description "ledger-reconciliation skill" --type skill

totebag project context
totebag workspace get --brief --recursive
```

That's the whole loop: describe a project, add tasks/skills to it, and `project context` is the
restore blob an agent reads. Point your agent at the bundled guide so it knows the rest of the
commands:

```bash
totebag --skill   
```

## What a project can hold

| Item | What |
|---|---|
| **notes** | one-line facts |
| **links** | URLs (typed) |
| **docs** | editable markdown documents |
| **assets** | arbitrary files |
| **tools / skills** | dependencies the project needs (file optional) |
| **lists** | schema-free entry collections, exportable as CSV |
| **tasks** | deferred future work, each with its own attachments |

Plus the project's own **description** and **instructions**. Everything you store carries a
description — so `project context` stays high-signal.

## Store location

`totebag` defaults to `~/.totebag`. Point it anywhere with `TOTEBAG_ROOT` (or `--root`) — the URL
scheme picks the backend:

```bash
export TOTEBAG_ROOT=s3://my-bucket/totebag
```

S3 and GCS need an extra: `totebag[s3]` / `totebag[gcs]`.

## Contributing

Prerequisites and the local development workflow are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT

## Credits

Icon: <a href="https://www.flaticon.com/free-icons/totebag" title="totebag icons">Totebag icons created by Khoirul Huda - Flaticon</a>
