# MediCloud — Implementation Plan

Each phase ends with a report: files created, what was implemented, commands to run it,
test results, and any open issues. **Work pauses for approval before each new phase.**
A phase is "done" only when its exit criteria have actually been run and have passed.

## Environment snapshot (dev machine, checked 2026-11-12)

| Tool | Status | Used in |
|---|---|---|
| Docker 29.8.2 / Compose v5.6.0 | Installed. **Docker Desktop engine was not running.** | 3, 4, 6, 7 |
| minikube 1.39.0, kubectl 1.36.1 | Installed, no cluster yet | 4, 8 |
| Terraform 1.16.5 | Installed | 5 |
| AWS CLI 2.36.50 | Installed. User `terraform-admin` (AdministratorAccess since Phase 5), region `ap-southeast-2`. Free-plan account. | 5–9 |
| Node 24.14.1 / npm 11.11 | Installed | 2 |
| Python 3.14.3 | Installed. Containers and CI use 3.13. | 2 |
| git 2.48 | Installed. Repo initialised on `main`, no commits yet. | all |
| Ansible | Not installed. It will run in a container. | 6 |
| Trivy | Not installed. It will run in a container. | 3, 7 |
| helm, gh, kind | Not installed and not required. `gh` is optional for Phase 7 convenience. | — |
| Hardware | 16 logical CPUs, 15.7 GB RAM | minikube: 4 CPU / ~5 GB |

## Phase 1 — Architecture and planning ✅

**Deliverables:**

- [`architecture.md`](architecture.md)
- this plan
- repo skeleton
- `.gitignore` and `.env.example`
- README

**Exit criterion:** you approve the architecture and the open decisions listed in the README.

## Phase 2 — Full-stack application ✅

**Backend:**

- Config, DB session, the 16 ORM models and the initial Alembic migration
- Auth (Argon2id + JWT) and role guards
- Services and routers for all modules in architecture §6
- Dashboard aggregation queries
- `/health/*`, `/metrics` and `/system/status`
- Deterministic seed data

**Frontend:**

- Vite + React + Tailwind v4 scaffold, layout (navy sidebar), auth flow, protected routes
- All 9 pages, wired to the real API
- Toasts, confirm dialogs, and loading / empty / error states

**Tests:**

- pytest against PostgreSQL: auth, RBAC, every router's happy path and key failure paths,
  and DB constraints such as double-booking and bed occupancy
- Vitest + RTL + MSW: component and API-integration tests

**Exit criteria:**

- `pytest` and `npm test` pass.
- `npm run lint` is clean.
- The app runs locally (Postgres via a single `docker run`, backend via uvicorn, frontend via Vite).
- Every dashboard figure comes from the API.

**What I'll need:** Docker Desktop running, for a throwaway Postgres container used by the tests.

## Phase 3 — Docker ✅

**Deliverables:**

- Multi-stage `backend/Dockerfile` and `frontend/Dockerfile` (non-root, health checks)
- `.dockerignore` files
- Root `docker-compose.yml`: postgres + volume, migrate, backend, frontend, custom network,
  and an optional `monitoring` profile

**Exit criteria:**

- `docker compose up --build` reaches healthy status for every service.
- Login works at `http://localhost:8080`.
- A Trivy image scan has run and its report is captured.
- Stop/restart/reset commands are documented and verified.

**What I'll need:** Docker Desktop running.

## Phase 4 — Kubernetes (minikube) ✅

**Deliverables:**

- `k8s/00…09` manifests, `01-secrets.yaml.example` and the secret-generation script
- NGINX Ingress Controller install steps
- HPA, NetworkPolicies, PDB
- Load-generator tool manifest
- EKS Kustomize overlay (rendered and validated only)

**Exit criteria:**

- `kubectl apply -f k8s/` brings everything up on minikube (`--cni=calico`).
- Pods are Ready and the app is reachable through the Ingress.
- A rolling update completes with no failed requests.
- The HPA scales up under load.
- Pod deletion self-heals.
- Data survives a Postgres pod restart.
- `kubeconform` passes.

**What I'll need:** approval to create a minikube cluster (about 5 GB RAM while running).

## Phase 5 — Terraform (AWS) ✅ (applied and verified on AWS)

**Deliverables:**

- `bootstrap/` (state bucket)
- Modules: `vpc`, `security-groups`, `iam`, `eks`, `ecr`, `rds`
- Root `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`
- `terraform.tfvars.example` and `backend.tf.example`
- Cost notes

**Exit criteria (no spend), all met:**

- `terraform fmt -check -recursive` and `terraform validate` pass.
- `terraform test` passes for every module (16/16, mock provider).
- TFLint reports no issues.
- `trivy config terraform/` has been reviewed: findings are fixed, accepted in code, or
  left open with a written explanation.

**Exit criteria (AWS, decision D37):**

- The CLI identity has the permissions the stack needs.
- `terraform plan` is run against the account (read-only, needs approval).
- With separate approval of the cost: `terraform apply`, the app is deployed to EKS and
  verified in a browser, then `scripts/aws-teardown.sh` destroys everything and
  `scripts/aws-leftovers.sh` confirms nothing is left billing.

## Phase 6 — Ansible ✅

**Deliverables:**

- `ansible/Dockerfile` (control node), `ansible.cfg`, `inventory.ini.example`, `playbook.yml`
- `group_vars/`, vault example
- Roles: `common`, `docker`, `monitoring_agent`, `app_config`, `app_deploy`, `k8s_deploy`, `healthcheck`

**Exit criteria:**

- `--syntax-check` and `ansible-lint` are clean.
- The `host` play runs green twice against an Ubuntu 24.04 EC2 instance (D37).
  The second run proves idempotency (`changed=0`).
- The `k8s` play deploys to EKS.

**What I'll need:** Docker Desktop running (the Ansible control node is a container), and
approval for a session's AWS environment plus a t3.micro instance ($0.0132/h).

## Phase 7 — CI/CD ✅ (CI green on GitHub; CD verified on EKS on 2026-11-13)

**Deliverables:**

- `.github/workflows/ci.yml` and `cd.yml`
- Documentation for the GitHub secrets, variables and environment

**Exit criteria:**

- The workflows pass `actionlint`.
- The CI workflow runs green on GitHub.
- CD deploys to EKS end to end during a work session while the cluster exists (D37).

**What I'll need:**

1. A GitHub repository. You create it, or I push once you approve.
2. Permission to commit and push.
3. You add the secrets and variables in the repo settings. I'll list the exact names.

## Phase 8 — Monitoring ✅

**Deliverables:**

- `monitoring/prometheus/` (Compose config + alert rules)
- `monitoring/grafana/` (provisioned datasource + dashboard JSON)
- `monitoring/k8s/` (Prometheus with RBAC, kube-state-metrics, Grafana)

**Exit criteria:**

- All Prometheus targets are UP.
- Every dashboard panel shows data on EKS (D37).
- Alert rules load.
- The error-rate panel reacts to induced 5xx errors.

## Phase 9 — Final integration ✅ (end-to-end run on 2026-11-13, deployment.md §5.3)

**Deliverables:**

- End-to-end run on AWS: provision → configure → CI/CD deploy → monitor → destroy ✅
- Fixes for any integration issues found
- `docs/deployment.md`, `docs/troubleshooting.md`, `docs/demo-guide.md` (a scripted
  15-minute demo with talking points) ✅
- Final README

**Exit criterion:** a clean clone runs by following the README alone.
