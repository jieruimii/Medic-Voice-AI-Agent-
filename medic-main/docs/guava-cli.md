> ## Documentation Index
> Fetch the complete documentation index at: https://docs.goguava.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# CLI Reference

> Commands, project configuration, and troubleshooting for the Guava CLI

`guava` is the primary interface for working with Guava. It handles authentication, project scaffolding, local runs, deployment, phone number provisioning, conversation history, org management, outbound campaigns, and WebRTC widget codes. Projects can be written in Python or TypeScript/Node — the base image you pick determines the runtime. The Guava SDK is included in the project template.

## Quick reference

| Command | Description |
| - | - |
| `guava login [--no-launch-browser]` | Authenticate via OAuth (browser-based) |
| `guava logout` | Clear stored credentials |
| `guava create [name] [flags…]` | Scaffold a new project (see `guava create` below) |
| `guava run [dir] [-- args…]` | Run the agent locally (Python via `uv`, Node via `tsx`) |
| `guava update [flags…]` | Update project configuration (replaces `deploy update`) |
| `guava self-upgrade` | Upgrade the `guava` CLI to the latest version |
| `guava deploy up [dir] [--rebuild]` | Build and deploy |
| `guava deploy down [target] [--id ID]` | Stop a deployment |
| `guava deploy purge [target] [--yes]` | Permanently delete a project and all its data |
| `guava deploy scale <replicas> [dir]` | Scale a running deployment |
| `guava deploy status [target]` | Check deployment state |
| `guava deploy logs [target] [-n N]` | Runtime logs (default 200, max 1000) |
| `guava deploy build-logs [dir] [--id ID]` | Get build log URL |
| `guava deploy list` (alias `ls`) | List all deployments |
| `guava deploy changed [dir]` | Check whether code changed since last deploy |
| `guava numbers list` (alias `ls`) | List owned phone numbers |
| `guava numbers buy [dir]` | Provision a phone number for this project |
| `guava conversations list [filters…]` | List conversations (calls) |
| `guava conversations get <call_id>` | Show conversation details |
| `guava conversations transcript <call_id>` | Show conversation transcript |
| `guava conversations recording <call_id> [-o path]` | Download recording (WAV) |
| `guava org` / `guava org list` | List organizations you belong to |
| `guava org use [org_id]` | Switch active org (interactive if omitted) |
| `guava campaigns list` (alias `ls`) | List outbound campaigns |
| `guava campaigns show <code>` | Campaign details and status counts |
| `guava campaigns pause <code>` / `resume <code>` / `delete <code>` | Lifecycle controls |
| `guava campaigns add-contacts <code> <file> [flags…]` | Upload contacts |
| `guava webrtc create-code [--ttl SEC]` | Create a WebRTC code |
| `guava widget [--ttl SEC]` | Mint a WebRTC widget code |
| `guava say <text> [flags]` | Generate text-to-speech audio from input |

## Targeting a project

Most commands take an optional positional argument that tells the CLI **which project** to act on. If you omit it, the CLI uses the **current directory** — so running commands from inside your project folder always works. There are two flavors:

| Flavor | Accepts | Used by |
| - | - | - |
| `[dir]` | A path to the project directory (defaults to `.`). | `run`, `deploy up`, `deploy scale`, `deploy build-logs`, `deploy changed`, `numbers buy`, `update` |
| `[target]` | A project directory (its `guava.toml` is read to find the project) **or** a project ID — the `gp-…` value shown by `guava deploy list`. | `deploy down`, `deploy status`, `deploy logs`, `deploy purge` |

The difference: `[dir]`-style commands need your project files on disk (they build, read config, or run code locally), so they only accept a path. `[target]`-style commands act on an already-deployed project, so they also accept a project ID — letting you manage a deployment from anywhere without the source checked out.

<Note>
  A `[dir]` argument that isn't a real directory silently falls back to the current directory. Double-check the path if a command seems to act on the wrong project.
</Note>

## Command reference

### `guava login`

Authenticates the CLI against Guava via OAuth. Opens your default browser to a sign-in page and stores the resulting credentials locally so subsequent commands can call the API on your behalf.

| Name | Type | Required | Description |
| - | - | - | - |
| --no-launch-browser | flag | No | Print the login URL instead of opening a browser. |

### `guava logout`

Clears stored credentials. No parameters.

### `guava create`

Scaffolds a new Guava project on disk. The base image sets the runtime: Python (`python-sandbox:*`) generates `main.py` + `pyproject.toml` and installs dependencies with `uv sync` (unless `--skip-deps` is set); TypeScript/Node (`node-sandbox:*`) generates `main.ts` + `package.json`, which you install yourself with `npm install` (or `pnpm install` / `yarn install`). Either runtime also writes `README.md`, a `guava-docs.md` reference for AI coding assistants, and the `guava.toml` config. For outbound projects it also creates the matching campaign on the server.

`guava create` runs in **interactive mode** by default — the CLI prompts for anything you don't pass. In **non-interactive mode** (when stdin is not a TTY, or when you pass `--no-prompt`), there are no prompts: required flags must be supplied or the command errors, and optional flags fall back to documented defaults.

**Positional argument**

| Name | Type | Required | Description |
| - | - | - | - |
| name | string | No | Project path or name. Defaults to current directory. |

**Non-interactive mode flags** — in interactive mode you can omit any of these and the CLI will prompt; in non-interactive mode they behave as noted under "Required".

| Name | Type | Required (non-interactive) | Description |
| - | - | - | - |
| --no-prompt | flag | No | Force non-interactive mode. Auto-enabled when stdin is not a TTY. |
| --direction | inbound \| outbound | Yes | Call direction for the project. The only flag that has no default. |
| --base-image | string | No | Sandbox base image; sets the runtime (`python-sandbox:*` → Python, `node-sandbox:*` → TypeScript/Node). Default `python-sandbox:3.14`. |
| --tier | seed \| fruit \| tree | No | Instance tier. Default `seed`. |
| --replicas | integer | No | Number of pod replicas. Default 1. |

Inbound-only (`--direction inbound`):

| Name | Type | Required (non-interactive) | Description |
| - | - | - | - |
| --phone | string | No | Phone source: E.164 number, `any` (first owned number), or `buy` (provision a new one). |

Outbound-only (`--direction outbound`):

| Name | Type | Required (non-interactive) | Description |
| - | - | - | - |
| --calling-windows | JSON | Yes | E.g. `[{"day":"monday","start":"09:00","end":"17:00"}]`. No default — must be supplied. |
| --campaign-name | string | No | Campaign name. Defaults to the project name. |
| --timezone | IANA TZ | No | Default detected from system. |
| --origin-number | string (repeatable) | No | E.164, `any`, or `buy`. Repeat for multiple. |
| --max-concurrency | integer | No | Max concurrent calls. Default 1. |
| --max-attempts | integer | No | Max attempts per recipient. Default 1. |
| --start-date | YYYY-MM-DD | No | Campaign start date. Default today. |
| --description | string | No | Free-form description used as outreach context. |

<Note>
  Passing an inbound-only flag with `--direction outbound` (or vice-versa) will result in an error.
</Note>

### `guava run`

Runs the agent locally on your machine. The runtime comes from `guava.toml`'s `base_image`; if there's no config, it's inferred from your manifest file (`pyproject.toml` → Python, `package.json` → Node). Python projects run `uv run main.py`; Node projects run `node --import tsx main.ts` (requires `node_modules` — run `npm install` first). Anything after `--` is forwarded straight to your entry point, which is useful for one-off flags your agent reads from `argv`.

| Name | Type | Required | Description |
| - | - | - | - |
| target | string | No | Project directory. Defaults to current directory. |
| -- args… | passthrough | No | Anything after `--` is forwarded verbatim to the entry point (`uv run main.py` for Python, `node --import tsx main.ts` for Node). |

### `guava update`

Edits the fields in `guava.toml` — project name, base image, and instance tier — without re-scaffolding the project. Use this whenever you want to bump the Python sandbox version or move between tiers.

Like `create`, `guava update` runs in **interactive mode** by default and prompts for each field, showing the current value as the default. In **non-interactive mode** (`--no-prompt` or no TTY), no prompts run and any field you don't pass simply keeps its current value — nothing is required.

| Name | Type | Required | Description |
| - | - | - | - |
| dir | string | No | Project directory. Defaults to current directory. |

**Non-interactive mode flags** — in interactive mode the CLI prompts for each of these; in non-interactive mode, any flag you omit leaves the existing value unchanged.

| Name | Type | Required (non-interactive) | Description |
| - | - | - | - |
| --no-prompt | flag | No | Force non-interactive mode. Auto-enabled when stdin is not a TTY. |
| --name | string | No | New project name. |
| --base-image | string | No | New base image. |
| --tier | seed \| fruit \| tree | No | New instance tier. |

<Note>
  `guava deploy update` has been removed. Running it will display a message directing you to use `guava update` instead.
</Note>

### `guava self-upgrade`

Updates the `guava` binary itself to the latest released version. No parameters.

### `guava deploy up`

| Name | Type | Required | Description |
| - | - | - | - |
| dir | string | No | Optional path to the project directory. Defaults to the current directory. |
| --rebuild | flag | No | Force a fresh build even if code has not changed. |

### `guava deploy down`

| Name | Type | Required | Description |
| - | - | - | - |
| target | string | No | A project directory, or a project ID (`gp-…`). Defaults to the current directory. |
| --id | string | No | Optional project ID to stop directly. |

### `guava deploy purge`

Permanently deletes a project's deployments, container images, uploaded bundles, build history, and database records. Call logs and conversation history are retained. Unlike `deploy down` (which just stops the running sandbox), this cannot be undone.

| Name | Type | Required | Description |
| - | - | - | - |
| target | string | No | A project directory, or a project ID (`gp-…`). Defaults to the current directory. |
| --yes | flag | No | Skip the confirmation prompt. Destructive — use with care. |

### `guava deploy scale`

Scales an already-running deployment up or down by setting the desired pod-replica count. Use this to handle traffic spikes or scale back when idle without redeploying.

| Name | Type | Required | Description |
| - | - | - | - |
| replicas | integer | Yes | Number of pod replicas. |
| dir | string | No | Project directory. Defaults to current directory. |

### `guava deploy status`

| Name | Type | Required | Description |
| - | - | - | - |
| target | string | No | A project directory, or a project ID (`gp-…`). If omitted, behaves like `deploy list`. |

### `guava deploy logs`

| Name | Type | Required | Description |
| - | - | - | - |
| target | string | No | A project directory, or a project ID (`gp-…`). Defaults to the current directory. |
| -n | integer | No | Number of log lines to retrieve (default 200, max 1000). |

### `guava deploy build-logs`

| Name | Type | Required | Description |
| - | - | - | - |
| dir | string | No | Project directory. Defaults to the current directory. |
| --id | string | No | Optional Cloud Build ID to look up directly. |

### `guava deploy list`

Lists all deployments for the authenticated user as a table (NAME, STATUS, REPLICAS, PROJECT ID). `ls` is an alias for `list`.

### `guava deploy changed`

| Name | Type | Required | Description |
| - | - | - | - |
| dir | string | No | Project directory. Defaults to the current directory. |

Checks whether project files have changed since the last deploy.

### `guava numbers list`

Lists every phone number your active org owns. `ls` is an alias for `list`. No parameters.

### `guava numbers buy`

| Name | Type | Required | Description |
| - | - | - | - |
| dir | string | No | Optional path to the project directory. Defaults to the current directory. |

Purchases a phone number and stores it in `guava.toml`. On the next deploy, the number is injected into your sandbox as the `GUAVA_AGENT_NUMBER` environment variable.

### `guava conversations list`

Lists past conversations (calls) for your active org, newest first. All filters are optional and can be combined; results are paginated via `--after`.

| Name | Type | Required | Description |
| - | - | - | - |
| --direction | inbound \| outbound | No | Filter by call direction. |
| --from | E.164 | No | Filter by from-number. |
| --to | E.164 | No | Filter by to-number. |
| --date-from | ISO 8601 date | No | Earliest start date (e.g. `2026-06-01`). |
| --date-to | ISO 8601 date | No | Latest start date. |
| -n, --limit | integer | No | Page size (1–100). Default 50. |
| --after | string | No | Pagination cursor (`next_cursor` from previous page). |

### `guava conversations get` | `transcript` | `recording`

Inspect a single past call by ID — `get` returns the metadata and outcome, `transcript` returns the speaker-by-speaker text, and `recording` downloads the raw audio.

All take a positional `call_id`. `recording` also accepts `-o, --output <path>` (default `<call_id>.wav`).

### `guava org`

Lists the orgs you belong to and lets you switch which one the CLI acts on. The active org determines which numbers, deployments, conversations, and campaigns the other commands see.

| Subcommand | Description |
| - | - |
| `list` (alias `ls`) | List the orgs you belong to. Also the default when no subcommand is given (`guava org`). |
| `use [org_id]` | Switch the active org. Omit `org_id` to pick interactively from the list. |

### `guava campaigns`

Manage outbound campaigns from the CLI: inspect their state, pause/resume/delete them, and upload contact lists. Each campaign is referenced by its `code`, a `gcmp-`-prefixed identifier (e.g. `gcmp-xxxxxxxxxxxxxxxxxxxx`) shown by `guava campaigns list` or on the dashboard.

| Subcommand | Description |
| - | - |
| `list` (alias `ls`) | List outbound campaigns. |
| `show <code>` | Show campaign details and per-status contact counts. |
| `pause <code>` | Pause an in-flight campaign. |
| `resume <code>` | Resume a paused campaign. |
| `delete <code>` | Delete a campaign. |
| `add-contacts <code> <file> [flags…]` | Upload contacts to a campaign from a file (see below). |

**`add-contacts` arguments**

| Name | Type | Required | Description |
| - | - | - | - |
| code | string | Yes | Campaign code (e.g. `gcmp-...`). |
| file | path | Yes | Contacts file. Format dispatched by extension: `.csv` (header row with `phone_number`; other columns become string entries in each contact's `data`), `.json` (array of objects), `.jsonl` / `.ndjson` (one object per line). |
| --allow-duplicates | flag | No | Upload contacts that are already on the campaign. |
| --accept-tos | flag | No | Confirm the contacts comply with the [Terms of Service](https://goguava.ai/terms). Required in non-interactive mode; otherwise prompted. |

Every contact must include a `phone_number` field in E.164 format (e.g. `+15555550100`).

### `guava webrtc create-code`

Creates a WebRTC code (`grtc-...`) and prints it to stdout. Attach an agent to it with `listen_webrtc`, then call it from the browser. Use `--ttl` for a code that auto-expires; omit it for one that stays valid indefinitely.

| Name | Type | Required | Description |
| - | - | - | - |
| --ttl | integer (seconds) | No | TTL for the WebRTC code. Omit for a permanent code. |

### `guava widget`

Mints a short code that lets a browser-based WebRTC widget connect to your deployed agent. Use `--ttl` for a code that auto-expires; omit it for one that stays valid indefinitely.

| Name | Type | Required | Description |
| - | - | - | - |
| --ttl | integer (seconds) | No | TTL for the WebRTC code. Omit for a permanent code. |

### `guava say`

Generates sample text-to-speech (TTS) audio from input. Allows testing for pronunciation and spelling outside of a live agent call. Returns a link to generated audio.

| Name | Type | Required | Description |
| - | - | - | - |
| -v, --voice | string | No | Voice to synthesize TTS audio. Defaults to grace; see [`set_persona()`](/sdk-reference/set-persona) for all available voices. |
| -l, --language | string | No | Language of utterance (default English). |
| -s, --sampling-rate | integer (Hz) | No | Sampling rate in hertz; must be either 8000 or 16000 (default 16000). |

## The `guava.toml` file

Every Guava project has a `guava.toml` file in its root directory, created by `guava create` or `guava deploy up`. It stores the project's configuration and deployment state. The CLI reads it to identify the project and track deployments.

<Note>
  Projects created with CLI versions 0.29.0 and lower will have a JSON `.guava` file. The CLI will automatically migrate to the new `guava.toml` on the next save.
</Note>

```toml guava.toml theme={null}
project_id = "auto-generated unique ID"
name = "your project name"
base_image = "python-sandbox:3.14"  # python-sandbox:* (Python) | node-sandbox:* (TypeScript/Node)
tier = "guava-seed"           # guava-seed | guava-fruit | guava-tree
replicas = 1
phone_number = "+15555555555"  # set by guava numbers buy or guava create --phone
call_direction = "inbound"     # inbound | outbound
org_id = "..."
```

## Instance tiers

| Tier | CPU | Memory | Use case |
| - | - | - | - |
| `guava-seed` | 1 | 1Gi | Development / testing |
| `guava-fruit` | 2 | 2Gi | Standard production |
| `guava-tree` | 4 | 4Gi | High-performance workloads |

## Base images & dependencies

When you create a project, you choose a base image. During deployment, your code and dependencies are built on top of this image to produce the final container that runs in the cloud. You can change the base image later with `guava update`.

The base image also determines the project runtime: `python-sandbox:*` images run Python, `node-sandbox:*` images run TypeScript/Node.

Available base images:

* `python-sandbox:3.14`
* `python-sandbox:3.13`
* `python-sandbox:3.12`
* `python-sandbox:3.11`
* `python-sandbox:3.10`
* `node-sandbox:26`
* `node-sandbox:24`
* `node-sandbox:22`

## Dependency detection

During the build, the system installs your dependencies automatically based on the files present in your project root. It checks each set of files in order and uses the first match.

**Python:**

| Files present | What happens |
| - | - |
| `uv.lock` + `pyproject.toml` | Installs with `uv sync --frozen` (locked, reproducible) |
| `poetry.lock` + `pyproject.toml` | Installs with `uv sync` |
| `pyproject.toml` (alone) | Installs with `uv sync` |
| `requirements.txt` | Installs with `uv pip install -r requirements.txt` |
| `requirements.in` | Installs with `uv pip install -r requirements.in` |

**Node / TypeScript:**

| Files present | What happens |
| - | - |
| `pnpm-lock.yaml` | Installs with `pnpm install --frozen-lockfile --prod` |
| `yarn.lock` | Installs with `yarn install --immutable` (Yarn Berry — Yarn Classic 1.x is not supported) |
| `package-lock.json` | Installs with `npm ci --omit=dev` |
| `package.json` (alone) | Installs with `npm install --omit=dev` |

For local Node runs (`guava run`), also run `npm install` (or `pnpm install` / `yarn install`) first so `node_modules` exists.

## Troubleshooting

* **"Please run `guava login`"** — Your session has expired or you haven't logged in yet. Run `guava login` to re-authenticate.
* **"No main.py / main.ts found"** — `deploy up` requires an entry point in your project directory (`main.py` for Python, `main.ts` for Node). Make sure you're running the command from the right folder.
* **Deploy didn't pick up my changes** — If nothing changed since the last deploy, the build step is skipped automatically. Use `guava deploy up --rebuild` to force a full rebuild.
* **Build failed** — Run `guava deploy build-logs` to see the full build output and diagnose the issue.
* **Missing files in deployment** — `deploy up` excludes `guava.toml`, hidden files/dirs, `__pycache__`, and `node_modules` from the upload. Make sure your files aren't in an excluded path.
* **Dependencies not installing** — The build system auto-detects dependencies from your manifest/lockfiles. For Python that's `pyproject.toml`, `requirements.txt`, `uv.lock`, `poetry.lock`, or `requirements.in`; for Node it's `package.json`, `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`. Make sure one is present in your project root. For local Node runs, also run `npm install` so `node_modules` exists.

## Example

```bash theme={null}
# Log in (opens browser)
guava login

# Create a new project
guava create my-agent --direction inbound

# Run locally
cd my-agent
guava run

# Deploy the project
guava deploy up

# Scale to 3 replicas
guava deploy scale 3

# View runtime logs
guava deploy logs -n 50

# Browse recent conversations
guava conversations list --direction inbound -n 20

# Download a call recording
guava conversations recording <call_id> -o call.wav

# Tear down
guava deploy down
```


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.