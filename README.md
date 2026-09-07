<p align="center">
  <img src="assets/totebag.png" alt="totebag" width="120" />
</p>

# totebag

**Portable, vendor-neutral project knowledge any AI Agentcan restore over a CLI.**

Built by [StratoNext](https://www.stratonext.ai).

---

Your context shouldn't live inside one vendor's chat history. `totebag` keeps a workspace of
**projects** - each with **docs, notes, links, lists, assets, a task list, the tools it needs, and
a day-by-day work journal** - as a plain, human-readable tree on disk (or in S3 / GCS). Any agent
that can run a shell command rehydrates a project's knowledge with one call, and writes back
what it learns. No server, no API keys, no lock-in.

```
$TOTEBAG_ROOT/
  config.yaml                 # store config: the default workspace
  workspaces/wsp_abc/
    workspace.md              # workspace metadata + default project
    projects/prj_abc/
      project.md              # description, instructions; notes/links/tools inline in front-matter
      docs/doc_x.md           # markdown + front-matter (title, description)
      lists/lst_v.md          # schema-free entries (JSONL body), exportable as CSV
      assets/ast_y/report.pdf # a stored file, alongside its asset.md metadata
      tasks/tsk_z/task.md     # a to-do, in its own folder with its attachments
      log.md                  # day-by-day work journal, appended
```

Everything you store must carry a **description** you write - the store rejects undescribed
content, so `project context` stays high-signal.

It's git-friendly, Obsidian-readable, and diffable. The "sink" is just a root URL.

## Install

```bash
uv tool install totebag            # or: pipx install totebag
```

Developing on `totebag` itself? See [CONTRIBUTING.md](CONTRIBUTING.md) for prerequisites and the
local development setup.

## 60-second quickstart

```bash
totebag init
PID=$(totebag project create --name "Payments API" --description "Billing service")
totebag project use $PID            # make it the active project (or use -p / TOTEBAG_PROJECT)

# project-scoped commands act on the active project - no id needed
totebag project update --instructions "Handles invoicing + Stripe webhooks."
totebag note add   "Webhooks retry 3x; idempotency key required."
totebag link add   --url https://stripe.com/docs --name "Stripe docs" --type documentation
totebag doc  add   --title "On-call runbook" --description "What to do at 3am" --stdin < runbook.md
totebag asset add  ./arch.pdf --description "Service topology v2"
totebag tool add   --name stripe-cli --description "calls the Stripe API" --restore "brew install stripe"
TID=$(totebag task add --title "Wire webhooks" --description "handle Stripe retries")
totebag task done  $TID --description "webhooks handled with idempotency keys"  # logs to the journal, drops the task

totebag project context            # <- the blob any AI Agent reads to restore knowledge
totebag search "idempotency"
```

Set the active project once with `totebag project use <id>` (stored per workspace), or override
per-command with `-p/--project <id>` or the `TOTEBAG_PROJECT` env var - same pattern as `-w` /
`TOTEBAG_WORKSPACE` for workspaces. `totebag config` shows the active workspace and project.

## Use it with any AI Agent

`totebag` is **agent-driven**: point your agent at the bundled skill and it knows the commands.

```bash
totebag --skill                    # prints SKILL.md - pipe/import it into your agent
```

Claude Code, Cursor, Cline, Codex - anything that can run a shell command shares the same
store, at the same time. Restore in one agent, write back from another.

## Save to S3 (same tree, zero code change)

The "sink" is just a root URL, so pointing `totebag` at an `s3://` bucket stores the exact same
OKF tree in S3 instead of on local disk. Three steps:

**1. Install the S3 extra** (pulls in [`s3fs`](https://s3fs.readthedocs.io)):

```bash
uv tool install "totebag[s3]"        # or: pipx install "totebag[s3]"
```

**2. Give it AWS credentials.** `totebag` stores no keys of its own - it uses the standard AWS
credential chain via `s3fs`/`boto3`. Any one of these works:

```bash
export AWS_ACCESS_KEY_ID=...        # env vars
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=eu-west-1
# ...or a shared profile in ~/.aws/credentials:
export AWS_PROFILE=my-profile
# ...or nothing at all when running on EC2/ECS/Lambda with an IAM role.
```

**3. Point the root at your bucket and prefix**, then use `totebag` exactly as on disk:

```bash
export TOTEBAG_ROOT=s3://my-bucket/totebag   # or pass --root on any command
totebag init                                # creates the first workspace in the bucket
totebag project list
```

`--root` overrides the env var per command, so you can target different buckets without re-exporting:

```bash
totebag --root s3://other-bucket/totebag project list
```

`file://` (default), `s3://`, and `gcs://` (install the `gcs` extra) all work the same way via
[`fsspec`](https://filesystem-spec.readthedocs.io). The store is git-diffable locally and
inspectable in the S3 console - same files, wherever it lives.

## Model

One **workspace** → many **projects**. Each project has:

| Type | What | Description |
|---|---|---|
| **docs** | editable markdown documents | required |
| **notes** | one-line facts | self-describing |
| **links** | URLs (typed) | - |
| **lists** | named collections of schema-free entries, exportable as CSV | required |
| **assets** | arbitrary files | required |
| **tools** | tools/skills the project needs, with a restore command | required |
| **tasks** | work to do, each in its own folder with attachments | required |
| **journal** | day-by-day log of work done | - |


## Contributing

Prerequisites and the local development workflow are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT

## Credits

Icon: <a href="https://www.flaticon.com/free-icons/totebag" title="totebag icons">Totebag icons created by Khoirul Huda - Flaticon</a>
