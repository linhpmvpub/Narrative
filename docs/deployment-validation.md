# Local deployment validation and remaining handoff

The local validation environment is not a public deployment. It uses disposable PostgreSQL databases and synthetic fixtures. Production secrets, DNS/certificates, an approved hosting environment and the actual Threadnote repository have not been supplied. Live delivery remains disabled.

## Verified configuration

`deploy/Dockerfile` builds a non-root application image from a digest-pinned Python 3.13 image, using captured dependency constraints. `requirements-validated.txt` records the tested Windows environment; `requirements-container.txt` records the actual Linux container packages. These are exact-version inventories, not wheel-hash lockfiles. Both were audited with pip-audit; OS/image package scanning is a separate remaining gate. GitHub Actions are pinned to resolved commit hashes and dependency audit jobs are configured; no remote workflow run is claimed.

`deploy/compose.yml` keeps the API on a private internal network with a read-only root filesystem, bounded memory/process count, no Linux capabilities, no-new-privileges and a tmpfs. The API uses one worker, no access logs, 32 concurrent connections and no trusted forwarded headers. A nonblocking operator replay guard rejects concurrent replay in that process; multi-instance deployments require a distributed lock before scaling beyond this configuration.

The nginx proxy has a separate edge network and binds only `127.0.0.1:8443`. It provides TLS, a 64 KiB body limit, header/body inactivity timeouts, 5 requests/second per source IP with a burst of 10, 10 concurrent connections/IP, upstream timeouts and no-store/no-referrer/nosniff headers. Admin routes return 403; docs and OpenAPI return 404 through this proxy. Operator access is separate and private. Limits are deployment defaults, not performance-tuned promises; per-account/distributed quotas and retention policies remain to be designed for the actual host.

Proxy access logs contain only source IP, method, status and duration. They exclude URI/query, Authorization and body values; ordinary error logging is suppressed to avoid leaking capability URLs. A loopback canary test found no test bearer/path/query values in local proxy/API logs. Host/cloud logs and monitoring must be separately configured. Metadata-only logs trade debugging detail for privacy; retain protected operational diagnostics deliberately.

## Local secrets and database connectivity

Compose reads these ignored files: `secrets/database_url`, `secrets/tls.crt`, `secrets/tls.key`. The application accepts `DATABASE_URL_FILE`, rejects conflicting DATABASE_URL configuration, and requires a PostgreSQL URL in the secret file. Never commit these files. The test certificate is self-signed for localhost and expires after one day; it was verified explicitly by the test client, not installed as a system trust root. It is not a production certificate.

For the smoke test, the disposable `rie-release-validation` PostgreSQL container was attached to `rie-staging-validation_private`. The API secret referenced that container's synthetic `rie_demo` database. In a real deployment, attach a separately provisioned PostgreSQL service to the private network and use a least-privilege application role; the disposable test superuser credentials are not a production configuration.

With replacement valid secrets and the correct private database available:

```powershell
docker compose --project-name rie-staging-validation --file deploy/compose.yml up --build --detach
docker compose --project-name rie-staging-validation --file deploy/compose.yml exec -T proxy nginx -t
```

Keep the loopback binding until the reviewed external TLS/ingress and identity integration are ready. Do not merely change it to a public interface. The smoke environment is stopped after validation; Docker Desktop remains available, and container/database state is retained for inspection. To restart the disposable database use `docker start rie-release-validation` before restarting Compose.

## PostgreSQL regression and recovery evidence

The disposable container publishes only `127.0.0.1:55432`. `rie_test` is exclusively for destructive test setup/teardown; `rie_demo` and `rie_restore` are separate synthetic databases. Never point TEST_DATABASE_URL at production data.

The drill used `pg_dump --format=custom` for `rie_demo`, restored with `pg_restore --no-owner --exit-on-error` into the new empty `rie_restore`, then used `python -m engine.verify_restore --output reports/postgresql-restore.json`. That command reads distinct URLs from RESTORE_SOURCE_URL/RESTORE_TARGET_URL and compares every table's row count/content digest without writing to either database or reporting credentials/row contents. **All 36 tables matched.**

The dump stays inside the disposable container at `/tmp/rie_demo.dump`. This validates backup/restore mechanics on synthetic data, not encryption, offsite retention, least-privilege restore roles, disaster-recovery timing or production backup procedures.

Evidence: `reports/postgresql-tests.xml`, `reports/release-sqlite-tests.xml`, `reports/postgresql-restore.json`, `reports/postgresql-F021-N08.json`, `reports/deployment-smoke.json`, `reports/log-redaction.json`, `reports/dependency-audit.json`, `reports/container-dependency-audit.json`.

Configuration references checked during implementation: [nginx request limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html), [nginx core timeouts/body limits](https://nginx.org/en/docs/http/ngx_http_core_module.html), [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/), and [PyPA pip-audit](https://github.com/pypa/pip-audit). No vulnerability scan guarantees that software has no unknown vulnerabilities.
