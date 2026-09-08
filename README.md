<p align="center">
  <img src="assets/totebag.png" alt="totebag" width="120" />
</p>

# totebag

**Portable, vendor-neutral project knowledge any AI Agent can restore over a CLI.**

Built by [StratoNext](https://www.stratonext.ai).

---

Your context shouldn't live inside one vendor's chat history. `totebag` keeps a workspace of
**projects** - each with **docs, notes, links, lists, assets, the tools it needs, and a task
list**.

Everything lives in a **store** - an abstraction over *where the bytes physically sit* (your local
filesystem, S3, or Google Cloud Storage), addressed by a single root URL. Any agent that can run a
shell command rehydrates a project's knowledge with one call, and writes back what it learns. No
server, no API keys, no lock-in. See [The store](#the-store-one-abstraction-many-backends) for the
backends and how to switch.

```
$TOTEBAG_ROOT/
  config.yaml                 # store config: the default workspace
  workspaces/wsp_abc/
    workspace.md              # workspace metadata + default project
    projects/prj_abc/
      project.md              # description, instructions; notes/links inline in front-matter
      docs/doc_x.md           # a document asset: editable markdown + front-matter
      lists/lst_v.md          # schema-free entries (JSONL body), exportable as CSV
      assets/ast_y/report.pdf # a byte asset: a stored file, alongside its asset.md metadata
      assets/tol_w/asset.md   # a tool/skill: an asset (category=tool, file optional)
      tasks/tsk_z/task.md     # deferred work to pick up later, in its own folder with attachments
```

Everything you store must carry a **description** you write - the store rejects undescribed
content, so `project context` stays high-signal. It's git-friendly, Obsidian-readable, and diffable.

## Model

One **workspace** → many **projects**. Each project has:

| Type | What | Description |
|---|---|---|
| **docs** | editable markdown documents | required |
| **notes** | one-line facts | self-describing |
| **links** | URLs (typed) | - |
| **lists** | named collections of schema-free entries, exportable as CSV | required |
| **assets** | arbitrary files | required |
| **tools** | tools/skills the project needs (an asset by category; file optional) | required |
| **tasks** | **future** work to do later - deferred/postponed items, one per folder with attachments | required |

**Tasks are for the future, not the present.** A task marks something to pick up *later* - a
deferred implementation, a follow-up, a known gap handed to the next session or agent. It is not a
tracker for work in progress; capture what you're learning now as **notes** or **docs**, and
remove each task the moment it's done so the list only shows real, still-open future work.

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
totebag tool add   --name stripe-cli --description "calls the Stripe API" --type tool
TID=$(totebag task add --title "Wire webhooks" --description "handle Stripe retries")
totebag task delete $TID --confirm   # drop it from the list once done

totebag project context            # <- the blob any AI Agent reads to restore knowledge
totebag search "idempotency"
```

**Choosing the active project.** Project-scoped commands (`note add`, `doc add`, `task add`,
`project context`, ...) act on whichever project is *active*, so you never repeat its id. Three
ways to set it, from most to least persistent:

- **`totebag project use <id>`** - makes it the default for the workspace; persists across
  commands and shell sessions.
- **`-p/--project <id>`** - overrides the active project for a single command.
- **`TOTEBAG_PROJECT=<id>`** - sets it for the current shell (an env var, so it survives across
  commands in that shell but not beyond it).

Workspaces work the same way: `totebag workspace use <id>`, `-w/--workspace <id>`, or
`TOTEBAG_WORKSPACE`. Run `totebag config` to see the active workspace and project.

## Use it with any AI Agent

`totebag` is **agent-driven**: point your agent at the bundled skill and it knows the commands.

```bash
totebag --skill                    # prints SKILL.md - pipe/import it into your agent
```

Claude Code, Cursor, Cline, Codex - anything that can run a shell command shares the same
store, at the same time. Restore in one agent, write back from another.

## The store: one abstraction, many backends

A **store** is where `totebag` persists everything - an abstraction over the physical storage
layer. Your commands never change based on where the bytes actually live: you address a store with
a single **root URL**, the URL scheme selects the backend, and every read and write is routed
through [`fsspec`](https://filesystem-spec.readthedocs.io). The exact same human-readable
**Open Knowledge Format (OKF)** tree round-trips to every backend, byte for byte.

Set the root once with the `TOTEBAG_ROOT` environment variable, or override it per command with
`--root`. With neither, `totebag` defaults to your local filesystem at `~/.totebag`.

```bash
export TOTEBAG_ROOT=s3://my-bucket/totebag        # default for this shell
totebag --root gcs://other-bucket/totebag ...     # one-off override for a single command
```

### Current stores

| Backend | Root URL | Install | Credentials |
|---|---|---|---|
| **Local filesystem** (default) | `file://<path>` | built in | none - just a writable path |
| **AWS S3** | `s3://<bucket>/<prefix>` | `totebag[s3]` | standard AWS chain (env vars, profile, IAM role) |
| **Google Cloud Storage** | `gcs://<bucket>/<prefix>` | `totebag[gcs]` | Application Default Credentials |

Because every backend stores the identical OKF tree, you can start local and move to the cloud
later with no migration beyond copying the files.

### Local filesystem (default, OKF)

Nothing to install or configure - `totebag init` creates the store under `~/.totebag`. Point it
anywhere with a `file://` root:

```bash
export TOTEBAG_ROOT=file:///data/totebag     # or: totebag --root file:///data/totebag ...
totebag init
```

The result is a plain, git-diffable, Obsidian-readable tree on disk (the layout shown at the top
of this README).

### Switch to AWS S3

**1. Install the S3 extra** (pulls in [`s3fs`](https://s3fs.readthedocs.io)):

```bash
uv tool install "totebag[s3]"        # or: pipx install "totebag[s3]"
```

**2. Give it AWS credentials.** `totebag` stores no keys of its own - it uses the standard AWS
credential chain via `s3fs`/`boto3`. Any one of these works:

```bash
export AWS_ACCESS_KEY_ID=...         # env vars
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

### Switch to Google Cloud Storage

**1. Install the GCS extra** (pulls in [`gcsfs`](https://gcsfs.readthedocs.io)):

```bash
uv tool install "totebag[gcs]"       # or: pipx install "totebag[gcs]"
```

**2. Give it Google credentials.** `totebag` stores no keys of its own - `gcsfs` uses Application
Default Credentials (ADC). Any one of these works:

```bash
gcloud auth application-default login       # local dev
# ...or a service-account key:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
# ...or nothing at all on GCE/Cloud Run/GKE with an attached service account.
```

**3. Point the root at your bucket and prefix**, then use `totebag` exactly as on disk:

```bash
export TOTEBAG_ROOT=gcs://my-bucket/totebag   # or pass --root on any command
totebag init                                 # creates the first workspace in the bucket
totebag project list
```

## Contributing

Prerequisites and the local development workflow are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT

## Credits

Icon: <a href="https://www.flaticon.com/free-icons/totebag" title="totebag icons">Totebag icons created by Khoirul Huda - Flaticon</a>
