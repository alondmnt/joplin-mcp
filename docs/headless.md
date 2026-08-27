# Headless Deployment (Experimental)

> **Status: experimental, community-supported.**
> This is **not** the recommended Docker setup. It runs a headless Joplin client
> stack so an MCP server / AI agent can operate on your notes without the Joplin
> Desktop app. It carries operational risk that a normal desktop client does not
> (upgrade and sync behaviour against a long-lived headless profile). Read the
> [Safety & failure modes](#safety--failure-modes) section before you rely on it,
> and **back up before every upgrade**.

## Why this exists

The standard Docker setup needs `JOPLIN_TOKEN`, which you can only get from the
Web Clipper settings of a **running Joplin Desktop instance**. That makes a fully
server-side deployment (VPS, NAS, CI) impossible.

This setup removes the Desktop dependency by running Joplin headlessly via
[`joplin-terminal-data-api`](https://github.com/RickoNoNo3/joplin-terminal-data-api)
(a headless Joplin CLI plus a small nginx proxy that auto-injects the Data API
token). You get a **headless participant** in your normal Joplin sync — your
phone and laptop keep syncing as usual; the server is just another client with no
GUI.

## Architecture

```
db (postgres) ── joplin-server ◄──sync──► your phone / laptop
                      ▲
                      │ sync target 9 (Joplin Server)
                 joplin-data-api   headless Joplin CLI + nginx token proxy (:41185 → :41184)
                      ▲
                      │ Joplin Data API (token auto-injected)
                 joplin-mcp        FastMCP server (:8000)  ◄── AI agents
```

| Service | Role | Published port |
| --- | --- | --- |
| `db` | PostgreSQL store for Joplin Server | none (private) |
| `joplin-server` | Joplin sync server | `8082` (for your other devices) |
| `joplin-data-api` | Headless Joplin CLI + token-injecting proxy | **none (private)** |
| `joplin-mcp` | This MCP server | `8000` |

## Pinned image versions

The compose file pins every image **by digest** (no `:latest`) so a redeploy is
reproducible and an upstream image change can never silently alter behaviour.

| Image | Tag | Tested with |
| --- | --- | --- |
| `postgres` | `16.14` | PostgreSQL 16.14 |
| `joplin/server` | `3.7.1` | Joplin Server 3.7.1 |
| `rickonono3/joplin-terminal-data-api` | digest-pinned | publishes `:latest` only; pinned by digest |
| `joplin-mcp` | built from this repo's `Dockerfile` | — |

To bump a version: change one digest, run the smoke tests below, then commit.
Rollback is reverting to the previous digest.

## Networking: keep the Data API private

The Joplin Data API has **no authentication of its own** in this setup — the
nginx proxy injects the token, so anything that can reach `:41185` has full
read/write access to your notes. Therefore:

- `joplin-data-api` and `db` publish **no host ports**; they live only on the
  internal `joplin_internal` network.
- Only `joplin-mcp` (on the same network) talks to the Data API.
- `joplin-server` is published on `8082` because your other devices must reach
  it to sync — put it behind a reverse proxy with TLS in production.

### Port choice: `41185` (auto-token proxy) vs `41184` (explicit token)

This setup uses **`41185`**, the nginx proxy port. The proxy strips any token a
client sends and injects the Joplin CLI's real token, so `joplin-mcp` can send a
placeholder. The token is managed entirely inside the container — you never copy
it into your environment.

The alternative is to connect directly to **`41184`** (the raw Joplin Data API)
and pass a real `JOPLIN_TOKEN`. That works too, but you must extract the token
from the profile and keep it in your `.env`. The proxy approach (`41185`) is
preferred for headless because there is no token to manage or leak.

## Volume layout & backup/restore

Two named volumes hold all state:

| Volume | Contents | Back this up |
| --- | --- | --- |
| `joplin_db` | PostgreSQL data (all notes, as synced by Joplin Server) | **yes** |
| `joplin_profile` | Joplin CLI profile: `settings.json`, `database.sqlite`, Data API token | **yes** |

**Back up before every upgrade.** Example (stop the stack first for a consistent snapshot):

```bash
docker compose -f docker/docker-compose.headless.yml stop
docker run --rm -v joplin_db:/data -v "$PWD":/backup alpine \
  tar czf /backup/joplin_db.tgz -C /data .
docker run --rm -v joplin_profile:/data -v "$PWD":/backup alpine \
  tar czf /backup/joplin_profile.tgz -C /data .
docker compose -f docker/docker-compose.headless.yml start
```

Restore is the reverse: recreate the volume and untar into it before starting.

## First-run bootstrap (one time)

Image env vars are **not** enough to configure sync — the sync target is stored
in the Joplin CLI profile, which you set once. After `docker compose ... up -d`:

1. **Create a sync user on Joplin Server.** Open `http://localhost:8082`, log in
   with the default admin (`admin@localhost` / `admin`), change the password, and
   (recommended) create a dedicated user for the headless client.

2. **Configure sync inside the Data API container** and do the first sync:

   ```bash
   docker compose -f docker/docker-compose.headless.yml exec joplin-data-api sh -lc '
     joplin config sync.target 9
     joplin config sync.9.path http://joplin-server:22300
     joplin config sync.9.username "you@example.com"
     joplin config sync.9.password "your-password"
     joplin sync
   '
   ```

   `sync.target 9` is **Joplin Server**. Other targets: `7` WebDAV, `5` Nextcloud,
   `8` Amazon S3, `2` local filesystem, `10` Joplin Cloud — adjust the `sync.*`
   keys accordingly.

3. **Verify** the MCP server can reach the notes:

   ```bash
   curl -s http://localhost:8000/mcp -H 'Accept: text/event-stream' | head
   ```

The token is generated and injected automatically; you do not configure it.

## End-to-end encryption (E2EE)

This setup is documented and tested with **E2EE disabled**. The headless Joplin
CLI must read and write note content in plaintext to serve the Data API, so:

- If your sync account has **E2EE enabled**, you must also set the master password
  in the CLI profile (`joplin e2ee decrypt` / configure the master key) for the
  headless client to read notes — otherwise it syncs only ciphertext and the MCP
  tools see nothing useful.
- Treat the `joplin_profile` volume as **highly sensitive** either way: it holds
  the Data API token and, if E2EE is enabled, the master key material.
- Recommendation: run the headless client on a trusted, access-controlled host and
  keep the Data API private (as configured).

## Safety & failure modes

The main concern with a headless client is an upgrade or sync error corrupting the
store. Mitigations built into this setup and workflow:

- **`sync.wipeOutFailSafe` (on by default):** Joplin refuses to propagate a delete
  of all notes when the remote suddenly looks empty — guards against a bad sync
  wiping your data. Leave it enabled.
- **Pinned digests:** an upstream image can't change under you; upgrades are
  deliberate and reversible by digest.
- **Backup before upgrade:** see above — the single most important habit.
- **Upgrade workflow:** back up → bump one image digest → `up -d` → run the smoke
  tests → confirm a successful `joplin sync` → only then continue. If anything
  looks wrong, restore the volumes and revert the digest.
- **Known caveats:** the headless CLI version and your other clients' versions can
  drift; after upgrading the Data API image, run a manual `joplin sync` and watch
  the logs (`docker compose ... logs joplin-data-api`) before trusting it.

## Smoke tests

```bash
# Static validation (no containers started)
docker compose -f docker/docker-compose.headless.yml config

# After bootstrap: confirm the MCP endpoint responds
curl -s http://localhost:8000/mcp -H 'Accept: text/event-stream' | head

# Confirm headless sync works
docker compose -f docker/docker-compose.headless.yml exec joplin-data-api \
  sh -lc 'joplin sync && joplin ls'
```

See also [`docs/agent-smoke-tests.md`](agent-smoke-tests.md) for MCP-level checks.
