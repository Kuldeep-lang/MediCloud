# MediCloud — Deployment Guide

This guide covers every way to run MediCloud, from simplest to most production-like. Each
section is added once its phase has been built and verified.

| Mode | Status | Section |
|---|---|---|
| Docker Compose (single host) | ✅ Verified (Phase 3) | [below](#1-docker-compose) |
| Kubernetes on minikube | ✅ Verified (Phase 4) | [§2](#2-kubernetes-minikube) |
| AWS: EKS + RDS via Terraform | ✅ Verified on AWS (Phase 5) | [§3](#3-aws-terraform--eks) |
| Ansible: EC2 server + EKS bootstrap | ✅ Verified (Phase 6) | [§4](#4-configuration-management-ansible) |
| CI/CD: GitHub Actions | ✅ CI green on GitHub · 🟡 CD verified in the next AWS session (Phase 7) | [§5](#5-cicd-github-actions) |
| Monitoring: Prometheus + Grafana on EKS | ✅ Verified (Phase 8) | [§6](#6-monitoring-prometheus--grafana-on-eks) |

For local development with hot reload (uvicorn + Vite), see the [README](../README.md).

---

## 1. Docker Compose

### 1.1 What runs

```
browser ──► http://localhost:8080
              │
         ┌────┴─────────────── network: medicloud-net ───────────────────┐
         │  frontend (nginx, UID 101)  ──/api──►  backend (FastAPI, UID 10001)
         │                                          │
         │  migrate (one-shot: Alembic + seed) ──►  postgres (PostgreSQL 17)
         │                                          └── volume: medicloud-pgdata
         └───────────────────────────────────────────────────────────────┘
```

| Service | Image | Published | Notes |
|---|---|---|---|
| `postgres` | `postgres:17-alpine` | no | Data persists in the named volume `medicloud-pgdata` |
| `migrate` | `medicloud-backend:local` | no | Runs `python -m app.db.prestart` and exits 0. Safe to re-run. |
| `backend` | `medicloud-backend:local` | **no** | Reached only through the frontend's `/api` proxy |
| `frontend` | `medicloud-frontend:local` | `127.0.0.1:8080` | Serves the SPA and proxies `/api` (and `/api/docs`) |

**Start-up order** is enforced by health checks:

1. `postgres` becomes healthy (`pg_isready`).
2. `migrate` completes successfully.
3. `backend` becomes healthy (`/health/live`).
4. `frontend` starts.

### 1.2 First run

```powershell
Copy-Item .env.example .env      # macOS/Linux: cp .env.example .env
```

Then edit `.env` and replace every `change-me` value. Generate strong values with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then start everything:

```powershell
docker compose up --build
```

Open **http://localhost:8080** and sign in as `admin@medicloud.demo` with your
`SEED_DEMO_PASSWORD`. API docs are at **http://localhost:8080/api/docs**.

If `POSTGRES_PASSWORD` or `JWT_SECRET_KEY` is missing, Compose refuses to start and tells
you which variable to set.

A cold first build takes about a minute. Later starts take about 20 seconds.

### 1.3 Everyday operations

| Task | Command |
|---|---|
| Start in the background | `docker compose up -d` |
| Start and rebuild after code changes | `docker compose up -d --build` |
| Status and health | `docker compose ps -a` |
| Follow logs (all services, or one) | `docker compose logs -f`  ·  `docker compose logs -f backend` |
| Restart everything (keeps containers and data) | `docker compose restart` |
| Restart one service | `docker compose restart backend` |
| Stop (keeps containers and data) | `docker compose stop` |
| Start again after stop | `docker compose start` |
| Remove containers and network (**keeps data**) | `docker compose down` |
| **Reset everything, including the database** | `docker compose down -v`, then `docker compose up -d` (re-seeds demo data) |
| Shell into the backend | `docker compose exec backend sh` |
| Run a SQL query | `docker compose exec postgres psql -U medicloud -d medicloud -c "select count(*) from patients"` |
| Re-run migrations by hand | `docker compose run --rm migrate` |

All of these were verified. Data survives `restart`, `stop`/`start` and `down`/`up`. Only
`down -v` deletes the `medicloud-pgdata` volume.

### 1.4 Configuration

All settings come from `.env`. See [.env.example](../.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | **required** | Database password |
| `JWT_SECRET_KEY` | **required** | Token signing key (32+ characters) |
| `SEED_DEMO_DATA` / `SEED_DEMO_PASSWORD` | `true` / — | Synthetic demo data and the demo accounts' password |
| `FRONTEND_PORT` | `8080` | Host port for the app |
| `APP_ENV` | `development` | `production` enforces a strong JWT key at start-up |
| `HOSPITAL_TIMEZONE`, `CURRENCY` | `Asia/Kolkata`, `INR` | Locale for "today" and money formatting |

Only the frontend port is published, and only on `127.0.0.1`. To reach the app from another
device on your network, change the port mapping in `docker-compose.yml` to
`"${FRONTEND_PORT:-8080}:8080"`.

### 1.5 Image design

| | Backend | Frontend |
|---|---|---|
| Build stage | `python:3.13-slim`: dependencies into `/opt/venv` | `node:24-alpine`: `npm ci && npm run build` |
| Runtime base | `python:3.13-slim` + copied venv | `nginxinc/nginx-unprivileged:stable-alpine` (nginx 1.30) |
| User | `medicloud` (UID 10001) | `nginx` (UID 101) |
| Size | ~350 MB | ~100 MB |
| Health check | `GET /health/live` (Python stdlib, no curl) | `GET /healthz` (busybox wget) |
| Hardening | OS packages upgraded at build; **pip removed**; code root-owned and read-only; bytecode pre-compiled | OS packages upgraded at build; envsubst limited to two variables |

**Runtime hardening in Compose:**

- `read_only: true`, with `tmpfs` only where a process must write.
- `cap_drop: [ALL]`. Verified `CapEff: 0` in the backend.
- `no-new-privileges`.
- CPU and memory limits on every service.

### 1.6 Security scanning

Images are scanned with **Trivy v0.69.3**, pinned by digest
`sha256:bcc376de8d77cfe086a917230e818dc9f8528e3c852f7b1aff648949b6258d1c`.

> **Why this exact version:** In March 2026 Trivy's release pipeline was compromised
> (CVE-2026-33634). Trivy v0.69.4–0.69.6 and most `trivy-action` tags shipped a credential
> stealer. v0.69.3 is a known-safe, immutable release. Never use `aquasec/trivy:latest` or
> unpinned action tags.

Commands (Git Bash). In PowerShell, drop `MSYS_NO_PATHCONV=1`:

```bash
# Vulnerabilities and embedded secrets in an image
MSYS_NO_PATHCONV=1 docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v medicloud-trivy-cache:/root/.cache aquasec/trivy:0.69.3 \
  image --scanners vuln,secret --ignore-unfixed --severity HIGH,CRITICAL medicloud-backend:local

# Dockerfile misconfigurations (scan one file at a time)
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)":/src:ro aquasec/trivy:0.69.3 \
  config /src/backend/Dockerfile
```

**Results at the end of Phase 3:**

| Scan | Backend | Frontend |
|---|---|---|
| Vulnerabilities with a fix available | **0** | **0** |
| All vulnerabilities | 201, all in Debian base packages with no upstream fix yet (0 critical) | **0** |
| Embedded secrets | 0 | 0 |
| Dockerfile misconfigurations | 27/27 checks passed | 27/27 checks passed |

The first scan found 5 fixable HIGH issues in libraries vendored inside **pip**: `urllib3`,
`msgpack` and `setuptools`. Removing pip from the runtime image cleared them. The CI pipeline
(Phase 7) will fail a build on any *fixable* HIGH or CRITICAL finding.

---

## 2. Kubernetes (minikube)

### 2.1 What runs

```
browser ─► http://medicloud.localhost:8081   (kubectl port-forward on Windows/macOS)
              │
   namespace nginx-ingress:  F5 NGINX Ingress Controller v5.7.0  (rate limits, routing)
              │  /  ─────────────────────►  frontend  Deployment ×2   (nginx, UID 101)
              │  /api  ──────────────────►  backend   Deployment 2–6  (FastAPI, UID 10001, HPA)
              │  /api/v1/auth/login (5/min) ─┘           │ initContainer: migrate + seed
   namespace medicloud (Pod Security: restricted, NetworkPolicy: default-deny)
                                                         ▼
                                              postgres  StatefulSet ×1 + PVC 1Gi
```

| Manifest | Contents |
|---|---|
| `00-namespace.yaml` | Namespace `medicloud` with Pod Security Admission `restricted` (enforced) |
| `01-secrets.yaml` | Generated and git-ignored. DB password, JWT key, demo password. |
| `02-configmap.yaml` | Non-secret settings (`APP_ENV=production`, timezone, DB host) |
| `03-postgres-statefulset.yaml` | Headless Service + StatefulSet + `volumeClaimTemplates`. Runs as UID 70 with a read-only root filesystem. |
| `04-backend-deployment.yaml` | ServiceAccount + Deployment |
| `05-frontend-deployment.yaml` | ServiceAccount + Deployment, 2 replicas, read-only filesystem with `emptyDir` for nginx's writable paths |
| `06-services.yaml` | ClusterIP `backend:8000`, `frontend:8080` |
| `07-ingress.yaml` | Mergeable Ingresses (master plus 3 minions): `/`, `/api` (20 r/s per IP), login (5 r/min per IP) |
| `08-hpa.yaml` | autoscaling/v2 HPA: CPU 70%, 2–6 replicas, scale up 2 pods/30 s, scale down 1 pod/min after 120 s |
| `09-policies.yaml` | 4 NetworkPolicies + 2 PodDisruptionBudgets |
| `ingress-controller/` | Kustomization pinning F5 NGINX Ingress Controller v5.7.0 (not applied by `-f k8s/`) |
| `tools/load-generator.yaml` | HPA demo load (not applied by `-f k8s/`) |
| `overlays/eks/` | Kustomize overlay for AWS (ECR images, RDS, no in-cluster DB) |

The backend Deployment uses:

- **2 replicas** and a **rolling update** with `maxSurge 1, maxUnavailable 0`.
- **A migrate initContainer** that runs migrations and the seed under an advisory lock.
- **Startup, liveness and readiness probes**. Liveness ignores the DB; readiness checks it.
- **A `preStop` drain** before shutdown.
- **Requests 100m/192Mi and limits 500m/512Mi.**

### 2.2 First-time setup

Prerequisites: Docker Desktop (8 GB or more), minikube, kubectl. Stop the Compose stack
first to free memory: `docker compose stop`.

```powershell
# 1. Cluster: Calico enforces NetworkPolicies; metrics-server feeds the HPA
minikube start --driver=docker --cpus=4 --memory=5g --cni=calico --addons=metrics-server

# 2. Ingress controller (pinned F5 NGINX Ingress Controller v5.7.0)
kubectl apply -k k8s/ingress-controller
kubectl rollout status deployment/nginx-ingress -n nginx-ingress

# 3. Build the images and load them into the cluster (no registry needed locally)
docker compose build
minikube image load medicloud-backend:local medicloud-frontend:local

# 4. Secrets: writes the git-ignored k8s/01-secrets.yaml with random values
python scripts/k8s_secrets.py

# 5. Deploy everything
kubectl apply -f k8s/
kubectl rollout status deployment/backend -n medicloud
```

### 2.3 Open the app

With the Docker driver on Windows and macOS, the minikube node IP isn't reachable from the
host, so forward a local port to the ingress controller. Keep this terminal open:

```powershell
kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80
```

Open **http://medicloud.localhost:8081**. API docs are at
**http://medicloud.localhost:8081/api/docs**. Browsers resolve `*.localhost` to your own
machine, so no hosts-file entry is needed.

Alternative: `minikube tunnel` (may need an admin terminal) and a LoadBalancer Service.

### 2.4 The everyday commands

| Task | Command |
|---|---|
| Pods / services / deployments | `kubectl get pods -n medicloud` · `kubectl get services -n medicloud` · `kubectl get deployments -n medicloud` |
| Inspect pods (probes, limits, events) | `kubectl describe pods -n medicloud` |
| Everything at once | `kubectl get all,ingress,pvc,hpa,networkpolicy,pdb -n medicloud` |
| Logs (app / migrations) | `kubectl logs -n medicloud deploy/backend` · `kubectl logs -n medicloud deploy/backend -c migrate` |
| Live CPU and memory | `kubectl top pods -n medicloud` |
| **Scale manually** | `kubectl scale deployment/frontend --replicas=3 -n medicloud` |
| Watch the autoscaler | `kubectl get hpa backend -n medicloud --watch` |
| Rolling restart (zero downtime) | `kubectl rollout restart deployment/backend -n medicloud` |
| Rollout progress / history | `kubectl rollout status deployment/backend -n medicloud` · `kubectl rollout history deployment/backend -n medicloud` |
| Emergency rollback | `kubectl rollout undo deployment/backend -n medicloud` |
| Shell in a pod | `kubectl exec -it -n medicloud deploy/backend -- sh` |

**Notes on scaling.**

- The **frontend** has no HPA, so a manual replica count sticks.
- The **backend** is owned by its HPA. A manual `kubectl scale` *within* 2–6 lasts only
  until the next HPA evaluation.
- Below 2, the HPA restores the minimum. This was verified: 1 became 2 within 10 s.
- To pin the backend size, edit `minReplicas`/`maxReplicas` in `08-hpa.yaml` and re-apply.

**Rollback.** `rollout undo` is the emergency lever: kubectl warns that it bypasses the
applied manifests. The normal path is to re-apply the previous image tag, which is what the
CD pipeline does.

### 2.5 Autoscaling demo

```powershell
kubectl apply -f k8s/tools/load-generator.yaml     # 3 pods hammering the backend Service
kubectl get hpa backend -n medicloud --watch       # replicas climb toward 6
kubectl delete -f k8s/tools/load-generator.yaml    # replicas drift back to 2
```

### 2.6 Verification results (Phase 4)

| Test | Result |
|---|---|
| `kubectl apply -f k8s/` from scratch | 22 resources created, no Pod Security warnings, all pods Ready |
| Schema validation (kubeconform v0.7.0, strict) | 24/24 resources valid (EKS overlay: 18/18) |
| App through the Ingress | Pages, deep links, API, login, Swagger ✅. `/metrics` and `/health` are not routed. Unknown host returns 404. |
| Migrations with 2 replicas starting together | One pod seeded; the other waited on the advisory lock and found the work done |
| **Zero-downtime rolling update** | **131/131 requests succeeded** while both backend pods were replaced (19 s) |
| **Self-healing** | Deleted backend and frontend pods were replaced automatically, back to 2/2 |
| **DB pod deleted** | `postgres-0` recreated on the **same PVC**; test patient still present |
| Probe design during the DB outage | Readiness failed and pods left rotation. **0 restarts** (liveness ignores the DB). |
| **HPA** | Under load: 2 → 4 → 6 (CPU 368%). After load: 6 → 2, one pod per minute after 120 s. |
| **NetworkPolicies enforced** | An intruder pod was blocked from postgres, backend and frontend. Frontend → postgres blocked. Allowed paths open. |
| **Ingress rate limits** | 12 rapid wrong logins gave 6× 401, then 6× 429. 30 normal API calls all passed. A 150-request flood had 23 rejected. |
| Load balancing | The monitoring page was answered by both backend pods |
| Manual scaling / rollback | frontend 2 → 3 → 2 ✅ · `rollout undo` ✅ |

### 2.7 Stop, resume, remove

| Task | Command |
|---|---|
| Pause the cluster (keeps everything, frees RAM) | `minikube stop` |
| Resume | `minikube start`, then re-run the `port-forward` |
| Remove the app only (**deletes the DB volume**) | `kubectl delete namespace medicloud` |
| Delete the whole cluster | `minikube delete` |

---

## 3. AWS (Terraform + EKS)

> **Verified on AWS on 2026-11-12/13** (decision D37). The stack was applied, the app was
> deployed to EKS and to an Ansible-managed EC2 server, monitoring was verified, and a
> database-outage experiment was run. The environment is **created at the start of each
> work session and destroyed at the end**, because it costs about $0.46/hour.
>
> **One account limitation:** this AWS account is not yet allowed to create load
> balancers (D39), so the EKS app is reached through `kubectl port-forward`, and the EC2
> server provides a public URL. See §3.4.

### 3.1 What runs on AWS

```
AWS account · ap-southeast-2 (Sydney)
├── VPC 10.20.0.0/16 (2 AZs)
│   ├── public  10.20.0.0/24, 10.20.1.0/24   → Internet Gateway, NAT Gateway, EC2 app server
│   ├── private 10.20.16.0/20, 10.20.32.0/20 → EKS nodes + pods, RDS
│   └── flow logs (REJECT only, 3-day retention) · default security group locked down
├── EKS 1.37 (API auth mode, KMS-encrypted secrets, upgrade policy STANDARD, audit logs)
│   ├── 2 × c7i-flex.large nodes (AL2023, IMDSv2, encrypted gp3), autoscaling 1–3
│   ├── add-ons: vpc-cni (NetworkPolicy on), kube-proxy, coredns, metrics-server
│   ├── namespace medicloud: frontend ×2, backend ×2–6 (HPA), Ingress, NetworkPolicies
│   ├── namespace nginx-ingress: F5 NGINX Ingress Controller v5.7.0
│   └── namespace medicloud-monitoring: Prometheus, kube-state-metrics, Grafana
├── RDS PostgreSQL 17 · db.t4g.micro · private · encrypted · TLS-only · 1-day backups (D40)
│   └── master password generated and stored by Secrets Manager (never in Terraform state)
├── EC2 app server (optional, Phase 6): Ubuntu 24.04 t3.small, configured by Ansible,
│   runs the same images from ECR with Docker Compose, node_exporter scraped by Prometheus
├── ECR: medicloud-backend, medicloud-frontend (immutable tags, scan on push, keep 10)
└── IAM: cluster, node, EC2 (ECR pull only) and GitHub OIDC deploy roles
```

| Terraform module | What it creates | Offline tests |
|---|---|---|
| `modules/vpc` | VPC, subnets, IGW, NAT, routes, flow logs | 4 |
| `modules/security-groups` | RDS security group (5432 from EKS only) | 1 |
| `modules/iam` | Cluster/node roles, GitHub OIDC provider + deploy role | 3 |
| `modules/eks` | Cluster, node group, add-ons, access entries | 4 |
| `modules/ecr` | Repositories + lifecycle | 1 |
| `modules/rds` | PostgreSQL instance, parameter group | 3 |
| `modules/app-host` | Ansible-managed EC2 VM, its security group and role | 4 |
| root `tests/stack.tftest.hcl` | Plans the whole stack from scratch with every option on | 2 |
| `bootstrap/` | Optional S3 bucket for remote state | — |

### 3.2 Cost

Sydney on-demand prices, **verified on 2026-11-12** from AWS's public Price List files.

| Resource | Configuration | USD / hour |
|---|---|---|
| EKS control plane | standard support | 0.1000 |
| Worker nodes | 2 × c7i-flex.large ($0.11072 each) | 0.2214 |
| NAT Gateway | $0.059/h, plus $0.059 per GB processed | 0.0590 |
| RDS PostgreSQL | db.t4g.micro + 20 GB gp3 | 0.0288 |
| EC2 app server | t3.small + 20 GB gp3 + public IPv4 | 0.0340 |
| Public IPv4 | NAT gateway address | 0.0050 |
| Node disks, KMS, Secrets Manager, CloudWatch, ECR | small | ~0.0150 |
| **Total** | | **≈ $0.46/hour ≈ $11/day** |

A Network Load Balancer would add about $0.04/hour once AWS allows it (D39).

**A work session** (about 30 minutes to build, a few hours of work, about 15 minutes to
destroy) costs **roughly $2**.

**Free-plan account constraints, found during the first apply (D38, D40):**

- **Server sizes.** Only Free-plan-eligible EC2 types can be launched. In Sydney those are
  t3/t4g/t8i micro and small, c7i-flex.large and m7i-flex.large, so the nodes use
  `c7i-flex.large` (same 4 GiB as a t3.medium).
- **Backups.** RDS rejects more than 1 day of backup retention (`FreeTierRestrictionError`).
- **Billing.** Charges come out of credits, and the account can't be billed beyond them.
  On a Paid plan, use `t3.medium` nodes and 7-day backups.

### 3.3 Start a work session

Prerequisites: AWS CLI credentials, Docker Desktop running, Git Bash. All commands run from
the repository root.

```bash
ansible/run.sh init                                 # once ever: SSH key + vault (Docker volume)

# 1. Infrastructure (~20 min). Allows SSH to the EC2 VM from the network you are on now.
scripts/app-host-access.sh
terraform -chdir=terraform init
terraform -chdir=terraform plan -out tfplan         # read-only: review what will be created
terraform -chdir=terraform apply tfplan             # starts billing

# 2. Build the images, push them to ECR and deploy to EKS (~8 min)
INGRESS_MODE=port-forward scripts/eks-deploy.sh

# 3. Configure the EC2 VM, bootstrap EKS and deploy monitoring with Ansible (~10 min)
INGRESS_MODE=port-forward ansible/run.sh playbook.yml
```

If your public IP changes during a session (for example, you move to campus Wi-Fi), run
`scripts/app-host-access.sh` and `terraform -chdir=terraform apply` again. Only the SSH
rule changes. If that network blocks outbound port 22, add `-e ansible_port=443` to the
Ansible command; sshd on the VM also listens on 443.

### 3.4 Open the app

| What | How |
|---|---|
| MediCloud on **EKS** | `kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80`, then open http://medicloud.localhost:8081 |
| MediCloud on the **EC2 server** | `http://<app_host_public_ip>` (`terraform -chdir=terraform output app_host_public_ip`) |
| **Grafana** | `kubectl port-forward -n medicloud-monitoring svc/grafana 3000:3000`, then open http://localhost:3000 (user `admin`) |
| Grafana password | `kubectl get secret grafana-admin -n medicloud-monitoring -o jsonpath='{.data.admin-password}' \| base64 -d` |
| **Prometheus** | `kubectl port-forward -n medicloud-monitoring svc/prometheus 9090:9090`, then open http://localhost:9090 |

Demo log-ins: `admin@medicloud.demo` (and the other roles in the README) with password
`Demo@12345`.

**Load balancer (D39).** AWS currently answers "This AWS account currently does not support
creating load balancers", a restriction it places on some new accounts. Two ways forward:

- **Optional:** ask AWS Support to lift it. Open a free case under **Account and billing**.
- **Once lifted:** re-run `scripts/eks-deploy.sh` without `INGRESS_MODE` to get a public NLB
  URL.

Until then, `INGRESS_MODE=port-forward` deploys the ingress controller with a NodePort.
Access then goes through the IAM-authenticated Kubernetes API.

### 3.5 End the session (always)

```bash
scripts/aws-teardown.sh       # deletes Kubernetes objects (and any NLB), terraform destroy, leftover check
scripts/aws-leftovers.sh      # read-only re-check at any time; exit code 0 = nothing billable left
```

`terraform destroy` on its own is not enough when an NLB exists, because Kubernetes created
it and Terraform doesn't know about it. The teardown script removes it first.

### 3.6 Verification results (2026-11-12/13)

| Check | Result |
|---|---|
| Offline: `terraform validate`, 22 mock-provider tests (7 modules + a whole-stack plan), TFLint, Trivy config | ✅ all pass. Trivy: 142 passed, 0 failed, accepted findings justified in code. |
| `terraform apply` (49 resources) | ✅ after one fix. The first apply created everything except RDS (`FreeTierRestrictionError` on 7-day backups). Retention was set to 1 and the re-apply created only the database. |
| `terraform plan` afterwards | ✅ "No changes", so there is no drift. |
| App on EKS (`eks-deploy.sh`) | ✅ 2 backend + 2 frontend pods Ready, 0 restarts. Images were pushed to ECR with an immutable tag. |
| Backend → RDS | ✅ PostgreSQL 17.9, **TLS 1.3**. Migrations and synthetic seed ran (120 patients, 1,753 appointments). |
| Browser check (headless Chrome) | ✅ log-in, dashboard, patients and monitoring pages. No console errors or failed requests. |
| Rolling update to a new image | ✅ rolled out with maxUnavailable 0 and the smoke test passed. Failed requests weren't counted during this rollout on EKS; on minikube (Phase 4) the same strategy served 131/131 requests. |
| Network Load Balancer | ❌ blocked by AWS for this account (D39). The app is served through port-forward instead. |
| EC2 app server (Ansible) | ✅ see §4.3 |
| Monitoring | ✅ see §6.3 |

### 3.7 Validation commands (offline, no AWS account)

```bash
cd terraform
terraform fmt -recursive -check && terraform init -backend=false && terraform validate
terraform test                                    # whole-stack plan (mock AWS)
for m in modules/*/; do terraform -chdir="$m" init && terraform -chdir="$m" test; done
tflint --init && tflint --recursive --config "$PWD/.tflint.hcl"
```

The public EKS API endpoint is an accepted finding (AWS-0040/0041, decision D37). It lets
GitHub-hosted runners deploy, and every request still needs AWS IAM authentication and an
EKS access entry. Set `cluster_endpoint_public_access_cidrs` to narrow it.

---

## 4. Configuration management (Ansible)

### 4.1 What Ansible does

Ansible runs in a **control-node container** (`ansible/Dockerfile`). It doesn't run
natively on Windows, and the container gives local runs and CI the same versions:
ansible-core 2.21.6, ansible-lint 26.10.1, AWS CLI, kubectl 1.37.2 and five pinned
collections.

`ansible/playbook.yml` has three plays:

| Play | Hosts | Roles | What it does |
|---|---|---|---|
| Resolve facts | localhost | — | AWS account, ECR registry and the newest image tag |
| `host` | `app_servers` (EC2, found by tag) | `common`, `docker`, `monitoring_agent`, `app_config`, `app_deploy`, then `healthcheck` | OS updates (and a reboot if the kernel changed), timezone, service user, Docker CE from Docker's signed repo, ECR credential helper, node_exporter as a sandboxed systemd service, Compose stack from ECR with secrets from **ansible-vault** |
| `k8s` | localhost → EKS | `k8s_deploy`, `monitoring_stack`, then `healthcheck` | Namespace, Secret built from **AWS Secrets Manager**, ingress controller, app manifests, monitoring stack, Grafana admin Secret, the EC2 scrape target, and end-to-end checks |

**Design points:**

- **Dynamic inventory.** `inventory/aws_ec2.yml` asks EC2 for running instances tagged
  `Role=app-server`, so no IP address is ever written down.
- **Secrets stay off disk.** The SSH key and vault password live in a Docker volume, never on
  the Windows filesystem. The vault file is encrypted and git-ignored.
- **Health checks from outside.** They run from the control node against the public
  address, covering the web page, the API and a real log-in, so they also test the
  security group.

### 4.2 Commands

```bash
ansible/run.sh init                         # once: SSH key, vault password, encrypted vault
ansible/run.sh lint                         # syntax check + ansible-lint (production profile)
ansible/run.sh inventory                    # hosts EC2 reports right now
ansible/run.sh playbook.yml --tags host     # configure + deploy the EC2 VM
INGRESS_MODE=port-forward ansible/run.sh playbook.yml --tags k8s         # EKS + monitoring
ansible/run.sh playbook.yml --tags host --check --diff                   # dry run
```

### 4.3 Verification results

| Check | Result |
|---|---|
| `--syntax-check`, `ansible-lint` (production profile) | ✅ 0 failures |
| SSH on port 22 and the 443 fallback | ✅ both answer |
| `host` play, first complete run | ✅ `changed=13, failed=0`. App healthy at `http://<public-ip>`, log-in OK. |
| `host` play, next run (idempotency) | ✅ **`changed=0`**, failed=0 |
| `k8s` play, first run | ✅ `changed=3`: Ansible took over objects first created by `kubectl` |
| `k8s` play, second run | ✅ **`changed=0`**, health check through the tunnel OK |
| Monitoring role, second run | ✅ **`changed=0`** |

The first run against a fresh VM hit a docker-ce packaging quirk: `docker.socket` was left
without a listening socket after install. The `docker` role now starts the socket before
the daemon, and recovers with a reset and retry if that fails (troubleshooting guide).

---

## 5. CI/CD (GitHub Actions)

### 5.1 Workflows

| Workflow | Trigger | Jobs |
|---|---|---|
| `.github/workflows/ci.yml` | every push to `main`, every PR | **backend**: ruff + pytest on a PostgreSQL 17 service container (coverage ≥ 85%) · **frontend**: eslint, vitest, build · **iac**: terraform fmt/validate/test, TFLint, kubeconform (incl. the rendered EKS overlay), ansible syntax + lint, shellcheck, Trivy config · **secrets**: gitleaks over full history · **images**: build both images with layer caching, Trivy fails on fixable HIGH/CRITICAL |
| `.github/workflows/cd.yml` | after CI succeeds on `main`, or by hand | OIDC to AWS → build (reusing CI's cache) → Trivy → push to ECR `:<sha>` → render the EKS overlay → `kubectl apply` → wait for rollout → smoke test → **automatic `rollout undo` on failure** |

**Supply chain:**

- Every third-party action is pinned to a full commit SHA.
- Trivy runs from an image pinned by digest. In March 2026, compromised Trivy releases and
  action tags were published (CVE-2026-33634).

**Two gates protect the bill and production:**

- the repository variable `DEPLOY_ENABLED` must be `true`;
- the `production` Environment must approve.

**Division of labour (D42):**

- **CD delivers the application only.** Its IAM role can push to the two ECR repositories,
  describe one cluster and edit the `medicloud` namespace.
- **Ansible's `k8s` play does the one-time cluster setup:** namespace, Secret, ingress and
  monitoring.

### 5.2 One-time GitHub setup

1. Push the repository to GitHub.
2. Allow it to deploy. Add this line to `terraform/terraform.tfvars` (git-ignored), then
   apply. This creates the OIDC provider, the deploy role and its EKS access entry. IAM is
   free.

   ```hcl
   github_repository = "<owner>/<repo>"
   # Only if the repository's OIDC subject uses immutable IDs (troubleshooting.md):
   github_owner_id      = "<owner.id from https://api.github.com/repos/<owner>/<repo>>"
   github_repository_id = "<id from the same URL>"
   ```

3. In the repository settings:

   | Kind | Name | Value |
   |---|---|---|
   | Environment | `production` | add yourself as a required reviewer |
   | Secret | `AWS_ROLE_ARN` | `terraform -chdir=terraform output -raw github_deploy_role_arn` (the same every session) |
   | Variable | `DEPLOY_ENABLED` | `true` only while the AWS environment is up |
   | Variable (optional) | `AWS_REGION`, `EKS_CLUSTER_NAME` | defaults are `ap-southeast-2`, `medicloud` |

No AWS keys are stored in GitHub, and no secret values appear in the workflow files.

**Run CD on a new commit.** ECR tags are immutable and both `eks-deploy.sh` and CD tag
images with the short commit SHA. If CD runs on the commit that `eks-deploy.sh` already
pushed, its `docker push` is refused. In a session, deploy the first version with
`eks-deploy.sh`, then push the next commit and let CI → CD deliver it.

### 5.3 Verification so far

**CI on GitHub** ([Kuldeep-lang/MediCloud](https://github.com/Kuldeep-lang/MediCloud/actions)):

| Run | Result |
|---|---|
| First push (`767faac`) | 5 of 6 jobs green. The IaC job failed at shellcheck: the runner's shellcheck 0.9.0 reported two findings that 0.11.0 locally did not. |
| Fix (`0dfd247`) | ✅ **all 6 jobs green**: backend, frontend, IaC, secret scan, both images. The two findings were fixed, and CI now runs a digest-pinned shellcheck 0.11.0 so local and CI results match. |

Until the AWS session, CD runs were **skipped**, as designed, because `DEPLOY_ENABLED` was
not set while no AWS environment existed.

**End-to-end session, 2026-11-13** (provision → configure → CI/CD deploy → destroy):

| Step | Result |
|---|---|
| `terraform apply` from nothing | ✅ **66 resources**, first from-scratch build since the D48 fix |
| `eks-deploy.sh` (port-forward mode) | ✅ version `b39b40a42779` rolled out, smoke test 200 |
| `ansible/run.sh playbook.yml` | ✅ failed=0 on both hosts. EC2 app, EKS bootstrap and monitoring health checks passed, demo login OK |
| CI on `1aadd8c` | ✅ all 6 jobs |
| CD attempt 1 | Skipped: the repository variable was misspelled (`DEPLOYED_ENABLED`) |
| CD attempt 2 | ❌ `Not authorized to perform sts:AssumeRoleWithWebIdentity`. CloudTrail showed GitHub's subject uses immutable IDs (`repo:Kuldeep-lang@172027358/MediCloud@1455658118:…`). Fixed in the IAM module (D49): a 1-resource, in-place trust-policy update |
| CD attempt 3 | ✅ approved in the `production` environment → OIDC → build → Trivy → push `1aadd8cf9ffa` → apply → rollout → smoke test |
| Independent check | ✅ both deployments on `:1aadd8cf9ffa` (rollout revision 1 → 2), 4/4 pods Running, 0 restarts, `/api/v1/system/info` answers |
| `aws-teardown.sh` | ✅ **66 destroyed**, leftovers check: nothing billable |

Before the first push, every check was also dry-run locally with the same tools:

| Step | Local result |
|---|---|
| actionlint 1.7.12 (incl. shellcheck of inline scripts) | ✅ clean |
| backend: ruff + pytest | ✅ **122 passed**, 91% coverage |
| frontend: lint, test, build | ✅ (Phase 2/3 results, unchanged code) |
| terraform fmt/validate/test, TFLint | ✅ |
| kubeconform: k8s manifests / EKS overlay / monitoring | ✅ 23/23, 18/18, 21/21 valid |
| ansible syntax + ansible-lint | ✅ |
| shellcheck | ✅ |
| Trivy config (Terraform + 3 Dockerfiles) | ✅ 0 HIGH/CRITICAL |
| gitleaks (staged tree) | ✅ no leaks |
| Trivy image scan, both images | ✅ 0 fixable HIGH/CRITICAL |

---

## 6. Monitoring (Prometheus + Grafana on EKS)

### 6.1 What runs

| Component | Version | Notes |
|---|---|---|
| Prometheus | v3.15.1 | Discovers pods and nodes through the Kubernetes API (read-only ClusterRole). Keeps 24 h of data in an emptyDir. |
| kube-state-metrics | v2.20.0 | Deployment, pod, restart and HPA state |
| Grafana | 13.3.1 | Datasource and **MediCloud Overview** dashboard provisioned from files; admin password in a generated Secret |

**What is scraped:**

- API pods (`/metrics`, pod-to-pod; never exposed through the Ingress);
- the ingress controller;
- kube-state-metrics;
- cAdvisor through the API server's node proxy;
- the EC2 server's node_exporter across the VPC. Ansible writes its private IP into a
  `file_sd` ConfigMap, and the security group admits port 9100 from the EKS cluster
  security group only.

Config lives once under `monitoring/` and `monitoring/k8s/kustomization.yaml` turns it into
ConfigMaps. All pods meet the `restricted` Pod Security Standard, and NetworkPolicies allow
only Grafana → Prometheus → kube-state-metrics.

**Dashboard rows:**

1. **Application health:** API pods up, database status, DB round-trip, 5xx rate, running
   build, EC2 status.
2. **API traffic:** requests by status class; p50/p95/p99 latency.
3. **Routes:** busiest API routes; 5xx by route.
4. **Kubernetes:** CPU and memory per workload, autoscaler replicas, ready pods, restarts,
   in-flight requests, throughput.
5. **Hospital gauges:** beds occupied, appointments today.
6. **EC2 server:** CPU, memory, disk.

The chart colours are the app's validated, colour-blind-safe palette.

**Alert rules** (Status → Alerts in Prometheus):

| Alert | Fires when |
|---|---|
| `BackendDown` | No backend pod is scraped for 1 minute |
| `HighErrorRate` | 5xx is more than 5% for 5 minutes |
| `HighLatencyP95` | p95 is over 1 second for 5 minutes |
| `PodRestartLoop` | A pod restarts more than 3 times in 15 minutes |
| `DatabaseDown` | `medicloud_db_up` is 0 for 1 minute |
| `AppHostDown` | The EC2 server stops reporting for 2 minutes |

### 6.2 Database-outage experiment (repeatable)

```bash
kubectl apply -f k8s/tools/chaos-block-database.yaml    # backend may no longer open DB connections
# end the backend's existing DB sessions (the VPC CNI only blocks *new* connections)
# - see the command in docs/troubleshooting.md "A NetworkPolicy doesn't stop existing traffic"
kubectl delete -f k8s/tools/chaos-block-database.yaml
kubectl rollout restart deployment/backend -n medicloud # required on VPC CNI v1.22 (see below)
```

**Observed on 2026-11-13** (while steady traffic ran):

| Time after start | What happened |
|---|---|
| seconds | Requests failed **fast** (500 within ~4 s, no hanging) thanks to the new DB timeouts (D44) |
| ~15 s | Readiness failed, so both API pods left the Service and clients received 502 from the ingress |
| ~1 min | `medicloud_db_up` = 0 and **`DatabaseDown` fired**. Prometheus could still scrape the pods, so the alert named the real cause rather than "API down". |
| throughout | `HighLatencyP95` and `HighErrorRate` went pending. **0 restarts**: liveness doesn't depend on the database, so Kubernetes didn't kill healthy pods. |
| recovery | After the policy was removed, pods could not resolve DNS until restarted. A rolling restart brought them back in about 20 s, and every alert cleared. |

The Grafana dashboard showed the 5xx burst, the latency ceiling, the failing readiness
route and the restart.

**Two findings from the experiment:**

1. **Missing DB timeouts.** The backend had no database timeouts, so a network partition
   would have blocked requests for up to about 15 minutes. Fixed: connect 3 s, TCP 4 s,
   keepalives and a pool timeout (D44), plus a test proving an unreachable database fails
   within seconds.
2. **VPC CNI network-policy behaviour.** The network-policy agent on VPC CNI v1.22 blocks
   only new connections, and removing an egress policy left the pods without DNS until they
   were restarted. This is recorded as a known limitation.

### 6.3 Verification results

| Check | Result |
|---|---|
| promtool: config syntax, rules | ✅ valid, 9 rules |
| kubeconform (rendered monitoring stack) | ✅ 21/21 |
| All Prometheus targets up | ✅ 8/8: prometheus, 2 API pods, ingress, kube-state-metrics, 2 × cAdvisor, **EC2 node_exporter** |
| Every dashboard panel shows data | ✅ after one fix: the 5xx rate now reads 0% instead of "No data" when no errors exist |
| Error-rate panel reacts to induced 5xx | ✅ §6.2 |
| Alert fires and resolves | ✅ `DatabaseDown` fired after 1 min and cleared after recovery |
