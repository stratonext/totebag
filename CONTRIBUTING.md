# Contributing to totebag

Thanks for your interest in improving totebag. This guide covers the prerequisites and the local
development workflow. For an architectural tour of the codebase, read [AGENTS.md](AGENTS.md).

## Prerequisites

- **Python 3.11+** - the project targets `>=3.11` (it uses `enum.StrEnum`).
- **[uv](https://docs.astral.sh/uv/)** - the package manager and runner used throughout. Install
  it with `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`).
- **[Task](https://taskfile.dev/)** (optional) - runs the shortcuts in `Taskfile.yml`. Install with
  `brew install go-task` or see the Task docs. Every task also has a plain-command equivalent shown
  below, so Task is not required.
- **git**, and for the cloud sinks, valid AWS/GCS credentials (only needed to exercise `s3://` /
  `gcs://`; the default `file://` sink needs nothing).

`ruff` is invoked via `uvx` and does not need a separate install.

## Set up locally

```bash
git clone <repository-url>
cd totebag
uv sync            # creates .venv with totebag (editable) + dev dependencies
```

`uv sync` installs the project in editable mode, so your source edits take effect immediately with
no reinstall. To work on the cloud sinks from a checkout, install their extras with
`uv sync --extra s3` and/or `uv sync --extra gcs`. Run the CLI straight from your working tree:

```bash
uv run totebag --help
uv run totebag --version
```

To get a `totebag` command on your PATH that tracks your checkout:

```bash
uv tool install --editable .        # or: pipx install -e .
```

Point the store at a throwaway location so development never touches real data:

```bash
export TOTEBAG_ROOT=file:///tmp/totebag-dev
uv run totebag init
uv run totebag project create --name scratch --description "throwaway"
```

## Everyday commands

Common tasks are wrapped in `Taskfile.yml`:

| Task | Plain command | What it does |
|---|---|---|
| `task install` | `uv sync` | Install package + dev deps |
| `task compile` | `uv run python -m compileall -q totebag tests` | Fast syntax check |
| `task test` | `uv run pytest -q` | Run the test suite |
| `task lint` | `uvx ruff check . --fix` | Lint (and auto-fix) with ruff |
| `task build` | `uv build` | Build the sdist and wheel into `dist/` |
| `task run -- <args>` | `uv run totebag <args>` | Run the CLI (e.g. `task run -- project list`) |

Run `task` with no arguments to list them.

## Making a change

Before opening a pull request:

1. **Add or update tests.** New behaviour needs a test; `tests/` uses `pytest` against a temporary
   `file://` store (see `tests/test_roundtrip.py` for the pattern).
2. **`task test` and `task lint` must both pass.** Lint is configured in `pyproject.toml`
   (`[tool.ruff]`); keep it clean rather than adding blanket ignores.
3. **Keep the code typed and documented.** Use type annotations throughout, Pydantic for data
   models, and a short docstring on public functions and classes. Code, comments, and commit
   messages are in English.
4. **Preserve the portability invariant.** Every model change must round-trip through the OKF
   on-disk format across the `file://`, `s3://`, and `gcs://` sinks without extra code - that
   portability is the point. `tests/test_roundtrip.py` guards it.
5. **Refresh the agent guide when the CLI changes.** `totebag/SKILL.md` is the agent-facing command
   reference bundled into the package; update it and any affected examples in `README.md`.
6. **Update the docs when behaviour or design changes.** Requirements live in
   `docs/requirements.md`; architecture and decisions live in `docs/architecture/` (ARCH documents,
   ADRs, and AARs). Add an ADR for a new architectural decision.

## Pull requests

- Keep each PR focused on **one concern**; smaller PRs review faster.
- Write commit messages in the imperative mood ("Add list export", not "Added").
- Describe what changed and why, and note any follow-ups.

## Continuous integration

Every push and pull request runs `.github/workflows/ci.yml`: ruff lint, tests on Python 3.11–3.13,
and a build (sdist + wheel) validated with `twine check`. Keep `main` green; enable branch
protection so these checks are required before merge.

## Releasing

Releases are driven by version tags via `.github/workflows/release.yml`:

Every tag — pre-release or final — **must point at a commit merged into `main`**, or the release
build fails; nothing publishes from a branch/PR tag. Merge the release PR first, then tag `main`.

- **`vX.Y.Z`** → publishes to [PyPI](https://pypi.org/project/totebag/).
- **Pre-release tags** (PEP 440 `rc`/`a`/`b`, e.g. `v0.2.0rc1`, `v0.2.0a1`) → publish to
  [TestPyPI](https://test.pypi.org/project/totebag/) so a build can be validated before a final tag.

Both publishes also pause for a manual approval on their GitHub Environment (`pypi` / `testpypi`)
before uploading.

To cut a release:

1. Update `CHANGELOG.md`: move items from `## [Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD`
   section.
2. Bump `version` in `pyproject.toml` (semantic versioning). Open a PR and **merge it to `main`**
   (`main` is protected: PR review + CI required).
3. **Tag the merged commit on `main`** and push the tag — the tag must match the `pyproject.toml`
   version:

   ```bash
   git checkout main && git pull
   git tag v0.1.0
   git push origin v0.1.0
   ```

The workflow verifies the tag matches the package version, requires the tag to be on `main`,
builds and metadata-checks the distributions, publishes them to the right index, and creates a GitHub
Release whose notes are the matching `CHANGELOG.md` section (falling back to auto-generated notes if
none is found). Pre-release tags are marked as pre-releases on GitHub.

### Verify a TestPyPI build

TestPyPI hosts only `totebag`, not its dependencies (`fsspec`, `pydantic`, ...), so the install
must fall through to real PyPI for those. Because a few deps also exist on TestPyPI, uv needs
`--index-strategy unsafe-best-match` to pick the newest version across indexes:

```bash
uv tool install \
  --index https://test.pypi.org/simple/ \
  --index https://pypi.org/simple/ \
  --index-strategy unsafe-best-match \
  totebag --prerelease=allow
totebag --version   # should print the rc you published
```

pip/pipx equivalent:

```bash
pipx install --pip-args="--index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ --pre" totebag
```

**One-time setup** (repository maintainer) — the workflow authenticates over OIDC, so no API tokens
are stored:

- On **PyPI**, configure a [Trusted Publisher](https://docs.pypi.org/trusted-publishers/) for the
  `totebag` project: GitHub owner/repo, workflow `release.yml`, environment `pypi`.
- On **TestPyPI**, configure the same trusted publisher with environment `testpypi`.
- Create matching GitHub Environments named `pypi` and `testpypi` (optionally with required
  reviewers to gate publishing).

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
