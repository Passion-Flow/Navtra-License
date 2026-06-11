# Forge Server Migration Guide (new server / new IP / new domain)

> Applies to the docker-compose deployment. For Helm deployments use this guide's asset inventory with Velero/VolumeSnapshot for the mechanics.
> Principle: **Forge is the revenue lifeline of every shipped product** — migrate by "rehearse first, run both servers in parallel, verify before cutover, keep a rollback". No step may take the old server offline before cutover completes.

---

## 0. Three things you must understand first

1. **The two KEKs are the crown jewels**: `FORGE_FIELD_ENCRYPTION_KEY` (master KEK) and `FORGE_EDGE_KEK` live in `.env`. The signing private keys are stored in PostgreSQL envelope-encrypted with these KEKs — **the database and the KEKs must migrate together**. Losing the KEKs = the private keys can never be unwrapped again = the entire issued-license ecosystem is dead (no key can ever sign for the public keys embedded in shipped products). This is unrecoverable.
2. **Offline customers are unaffected**: products activated with an offline `.forge` file never talk to Forge.
3. **Online customers depend on the endpoint form** (see `00-Global/licensing.md` [2026-06-11] endpoint durability standard):
   - **Domain era** (dedicated licensing domain pointing at Forge): migration = one DNS record change; customers never notice.
   - **IP era** (current transition: products' deploy env points at a raw IP): a new server means a new IP — every product deployment's `*_FORGE_EDGE_URL` must be updated, with the lease grace period as the safety net. **This is exactly why the domain purchase is urgent.**

### Asset inventory (every row required)

| Asset | Location (inside deploy dir) | Contents | Must migrate |
|---|---|---|---|
| PostgreSQL data | `volumes/postgres` (exported via pg_dump) | customers/products/licenses, **KEK-encrypted signing private keys**, online leases/seats, audit | ✅ |
| `.env` | `.env` | **both KEKs**, DB/Redis passwords, ports, mail, everything | ✅ |
| File storage volume | `volumes/storage` | forge-shared/storage (generated license files, etc.) | ✅ |
| Redis volume | `volumes/redis` | cache + Celery queue (AOF) | recommended (losing it only drops in-flight queue tasks) |
| Deploy files | `docker-compose.yaml` / `init/` / `Scripts/` | ship with the release tarball; re-extract on the new server | via release tarball |
| Images | Aliyun ACR | re-`docker compose pull` on the new server | re-pull |

---

## 1. Prepare the new server

1. Install Docker Engine + Compose plugin (`docker compose version` works).
2. **Security group**: open TCP 80 (forge-web admin) and TCP 8081 (forge-edge public validation). Restrict 80 to vendor office IPs if possible; 8081 must be reachable by customers.
3. Extract the **same version** Forge release tarball (e.g. `forge-docker-compose-1.0.0.tgz`) into the deploy dir. Do **not** run `cp .env.example .env` — the restore step brings the old `.env`.
4. Configure registry login: `bash Scripts/generate-image-repo-secret.sh` (docker login to ACR).
5. Confirm clock sync: `timedatectl` (signature and lease verification are time-sensitive; NTP must be on).

## 2. Back up the old server

```bash
cd <deploy dir>            # where docker-compose.yaml and .env live
# Hot backup for rehearsal (no downtime):
bash migration/Scripts/backup-forge.sh
# Final backup for the real cutover (briefly stops the app tier to freeze writes; postgres/redis stay up; auto-restarts after):
bash migration/Scripts/backup-forge.sh --final
```

Output: `forge-migration-<timestamp>.tar.gz`. Transfer it:

```bash
scp forge-migration-*.tar.gz user@<new-server>:/opt/
```

⚠ The archive contains the KEKs and all licensing data: encrypted channels only (scp/sftp); delete intermediate copies after transfer; long-term copies must be stored encrypted (`age`/`gpg`, then object storage).

## 3. Restore on the new server

```bash
cd <new deploy dir>
bash migration/Scripts/restore-forge.sh /opt/forge-migration-<timestamp>.tar.gz
```

Script order: verify SHA256 → place `.env` + storage/redis volumes → pull images → start postgres alone (first boot creates the restricted edge role + audit REVOKE via init scripts) → `pg_restore --clean` → start the full stack → wait for forge-api healthy.

## 4. Verification checklist (cutover is forbidden until all pass)

```bash
# 4.1 container health
docker compose ps        # forge-api / forge-edge / forge-web must be healthy

# 4.2 probes
curl -fsS http://127.0.0.1:8081/livez && echo OK-edge
curl -fsS http://127.0.0.1/ -o /dev/null -w '%{http_code}\n'   # forge-web 200

# 4.3 public key identity (the critical one — proves the private keys migrated AND the KEKs unwrap them)
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose master
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose edge_lease
# Output must match the old server byte-for-byte. Any mismatch = STOP; check .env KEKs and the DB restore.
```

4.4 Log into the admin (`http://<new-IP>`): customers, products, **license count equals the old DB**, audit history visible.
4.5 Trial issuance: issue an offline license for a test customer → verify it activates (any consumer product, or `forge-verify offline <blob>`).
4.6 Real edge activation: issue an **online** code for a test deployment and activate from the public internet; confirm a lease is returned.

## 5. Cutover

### Domain era (standard path)
1. Lower the licensing domain's DNS TTL to 300s **24–48h in advance**.
2. After the checklist passes, switch the A record to the new IP.
3. **Keep the old server running ≥ 72h** (some resolvers ignore TTL); watch old-server 8081 traffic drain to zero.
4. Optional hardening: run nginx on the old box reverse-proxying 8081/80 to the new IP for a few more days.

### IP era (current transition)
1. After verification, update every consumer product deployment's `*_FORGE_EDGE_URL` to the new IP and restart those components.
2. During the window, online customers keep running on their **cached signed lease** until `grace_until` — keep the window shorter than the smallest grace period.
3. Keep the old server up 72h after all products are switched.
4. Any customer you cannot reach in time: rescue with an **offline `.forge`** (the dual-track design is its own disaster recovery).

## 6. Decommission the old server

- After 72h of zero traffic and a re-run of the checklist: `docker compose down`.
- Securely erase `volumes/` and `.env` on the old disk (`shred` / encrypted-disk destruction). Never hand a disk containing KEKs back to the cloud provider.
- Archive the final backup encrypted (one off-site + one offline copy, per backup-recovery.md 3-2-1).

## 7. Rollback

If anything goes wrong after cutover: point DNS (or product env) back at the old IP — the still-running old server *is* the rollback plan. **Note**: licenses issued on the new server during the window stay in the new DB; before rolling back, export that delta (audit page) and re-issue each on the old server.

## 8. Changing the domain (decoupled from server moves — summary)

Per `00-Global/licensing.md` [2026-06-11] §D: run old + new domains in parallel → (once SDK steering ships) push the new endpoint list via signed lease responses → keep the old domain as 301/proxy for years → **never release the old licensing domain registration**.

## 9. Drill requirement

Per backup-recovery.md: at least **quarterly**, run "backup → restore on a scratch VM → checklist 4.1–4.6" without cutover. A full rehearsal is mandatory before the first real migration.

---

## Appendix A: Fully manual migration (no scripts, command by command)

> The scripts in §2/§3 merely codify the commands below. Run everything from the **deploy dir** (where `docker-compose.yaml` and `.env` live).

### A.1 Old server: manual backup

```bash
cd <deploy dir>

# 1) Confirm both KEKs are present (neither empty nor #REPLACE_ME#)
grep -E '^(FORGE_FIELD_ENCRYPTION_KEY|FORGE_EDGE_KEK)=' .env

# 2) Freeze writes for a real cutover (skip when rehearsing): stop app tier only
docker compose stop forge-api forge-edge forge-worker forge-scheduler forge-web

# 3) Dump the database (-Fc custom format: encrypted signing keys, licenses, leases, audit)
docker compose exec -T postgres pg_dump -U forge_app -d forge_main -Fc > forge_main.dump
#    If you changed them in .env, use DATABASE_USERNAME / DATABASE_NAME values instead

# 4) Pack the persistent volumes
tar czf storage.tar.gz -C volumes storage
tar czf redis.tar.gz   -C volumes redis            # optional but recommended

# 5) Copy .env (the most sensitive file — both KEKs inside)
cp .env env-backup && chmod 600 env-backup

# 6) Checksums + final archive
sha256sum forge_main.dump storage.tar.gz redis.tar.gz env-backup > SHA256SUMS   # macOS: shasum -a 256
tar czf forge-migration-manual.tar.gz forge_main.dump storage.tar.gz redis.tar.gz env-backup SHA256SUMS
chmod 600 forge-migration-manual.tar.gz
rm forge_main.dump storage.tar.gz redis.tar.gz env-backup SHA256SUMS

# 7) Bring the old server back up (it must stay online until cutover completes)
docker compose up -d

# 8) Transfer over an encrypted channel only
scp forge-migration-manual.tar.gz user@<new-server-IP>:/opt/
```

### A.2 New server: manual restore

```bash
# 1) Prereqs: Docker + Compose, security group 80/8081 open, release tarball extracted,
#    registry login done, NTP on
docker compose version && timedatectl | grep -i ntp

cd <new deploy dir>

# 2) Unpack and verify the backup
mkdir -p /opt/forge-restore && tar xzf /opt/forge-migration-manual.tar.gz -C /opt/forge-restore
cd /opt/forge-restore && sha256sum -c SHA256SUMS && cd -      # STOP on any failure

# 3) Place .env and volumes (volumes/postgres must be EMPTY — fresh machines only)
cp /opt/forge-restore/env-backup .env && chmod 600 .env
mkdir -p volumes
tar xzf /opt/forge-restore/storage.tar.gz -C volumes
tar xzf /opt/forge-restore/redis.tar.gz   -C volumes

# 4) Pull images; start postgres alone (first boot runs init/01-roles-and-audit.sh:
#    restricted edge role + audit-table REVOKE)
docker compose pull
docker compose up -d postgres
watch -n2 'docker compose exec -T postgres pg_isready'        # Ctrl-C when ready

# 5) Restore the database
docker compose exec -T postgres pg_restore -U forge_app -d forge_main \
  --clean --if-exists --no-owner < /opt/forge-restore/forge_main.dump

# 6) Start the full stack and wait for health
docker compose up -d
watch -n3 'docker compose ps'                                  # Ctrl-C when api/edge/web healthy

# 7) Clean up intermediates
rm -rf /opt/forge-restore /opt/forge-migration-manual.tar.gz
```

### A.3 Manual verification (same as §4 — all must pass)

```bash
docker compose ps
curl -fsS http://127.0.0.1:8081/livez
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose master
docker exec $(docker compose ps -q forge-api) forge keys export-public --purpose edge_lease
# Compare both PEMs byte-for-byte with the old server; then check license counts in the admin,
# issue a trial offline license, and perform one real online activation from outside.
```

### A.4 Manual cutover / rollback

Identical to §5/§7 (cutover is a DNS- or product-env-level action; there is no script by design): switch the A record in the domain era, or update each product's `*_FORGE_EDGE_URL` in the IP era; the old server kept alive for 72h is the rollback plan itself.
