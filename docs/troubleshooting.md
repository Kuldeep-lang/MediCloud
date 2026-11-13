# MediCloud — Troubleshooting

Real problems hit while building this project, and how to fix them. New entries are added
as each phase surfaces them.

## Local development

### Database connections hang for several seconds (Windows)

**Symptom:** Alembic or the API seems frozen at start-up; `psycopg` connects slowly.

**Cause:** On Windows, `localhost` resolves to IPv6 `::1` first. Docker publishes the port
on IPv4 `127.0.0.1` only, so every connection waits for the IPv6 attempt to time out.

**Fix:** Use `127.0.0.1` in `DATABASE_URL`, not `localhost`. `backend/.env.example` already
does this.

### `docker run`: "flag needs an argument: 'e' in -e"

**Cause:** A command split over several lines broke when pasted. PowerShell's backtick
(`` ` ``) continuation fails if any character, even a space, follows it. `cmd` and bash use
different continuation characters altogether.

**Fix:** Put the command on one line. All commands in the README are single-line.

### `GET / HTTP/1.1" 404` from uvicorn

This is expected. Port 8000 is the API, which only serves `/api/...`, `/health/...` and
`/metrics`. In development the app runs at **http://localhost:5173**; with Docker Compose it
runs at **http://localhost:8080**.

### A port is already in use

Find the owner before stopping anything:

```powershell
netstat -ano | findstr :8080
Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select-Object CommandLine
```

Compose publishes only port 8080 for the frontend, so it can run next to the dev servers on
8000 and 5173. To use a different host port, set `FRONTEND_PORT` in `.env`.

## Docker Compose

### Compose refuses to start: "required variable ... is missing a value"

`.env` is missing or incomplete. Run `Copy-Item .env.example .env` and set
`POSTGRES_PASSWORD` and `JWT_SECRET_KEY`. This guard is deliberate: the stack never starts
with empty secrets.

### `migrate` exited with a non-zero code

Check `docker compose logs migrate`. Common causes:

| Log message | Fix |
|---|---|
| `SEED_DEMO_PASSWORD must be set` | Set it (8+ characters) in `.env`, or set `SEED_DEMO_DATA=false` |
| Password authentication failed | The volume was created with a different `POSTGRES_PASSWORD`. PostgreSQL keeps its original password. Either restore the old value, or reset with `docker compose down -v` (this deletes data). |

### The app loads but every API call returns 502

The backend is down or unhealthy. Check `docker compose ps` and `docker compose logs backend`.

nginx re-resolves the backend's address every 10 seconds, so after the backend is recreated
the frontend recovers by itself. This was verified by forcing the backend onto a new IP.

### Scanning with Trivy from Git Bash fails to mount the Docker socket

Git Bash rewrites `/var/run/docker.sock` into a Windows path. Prefix the command with
`MSYS_NO_PATHCONV=1`, or run it from PowerShell.

## Kubernetes (minikube)

### Pods stuck in `ErrImagePull` / `ImagePullBackOff`

The cluster can't see the local images, because minikube has its own container store. Run
`docker compose build`, then `minikube image load medicloud-backend:local medicloud-frontend:local`.
After rebuilding an image, load it again and restart the deployment with
`kubectl rollout restart deployment/backend -n medicloud`.

### Pods stuck in `CreateContainerConfigError`

The Secret is missing. Run `python scripts/k8s_secrets.py`, then `kubectl apply -f k8s/`.

### `http://medicloud.localhost:8081` doesn't load

The port-forward isn't running, or it died after a pod restart. Restart it with
`kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80`.

Then check the ingress controller with `kubectl get pods -n nginx-ingress`. A request with
any other Host header returns 404 by design: the Ingress only serves `medicloud.localhost`.

### Login returns `429 Too Many Requests`

The Ingress rate limit is working: 5 login attempts per minute per client IP, plus a burst
of 5. Wait about a minute.

Through `kubectl port-forward` every request appears to come from the same IP, so repeated
test logins hit the limit quickly.

### HPA shows `cpu: <unknown>/70%`

metrics-server needs about a minute after start-up. Check it with `kubectl top pods -n medicloud`.
If it stays unknown, run `minikube addons enable metrics-server`.

### A new pod is rejected with "violates PodSecurity restricted"

The `medicloud` namespace enforces the *restricted* standard. Every pod must:

- run as non-root;
- set `allowPrivilegeEscalation: false`;
- drop `ALL` capabilities;
- use `seccompProfile: RuntimeDefault`.

See `k8s/tools/load-generator.yaml` for a compliant example.

### A pod can't reach another service

NetworkPolicies default to deny. Only the paths listed at the top of `k8s/09-policies.yaml`
are allowed. A new client needs its own policy, like the one shipped in
`k8s/tools/load-generator.yaml`.

### `rollout undo` warns about `last-applied-configuration`

This is expected. Undo bypasses the manifests, so the next `kubectl apply -f k8s/` puts
back whatever the files say. Treat undo as the emergency lever and the manifests (or CD) as
the source of truth.

### Background terminals left running

On Windows, stopping a shell doesn't always stop its child process, for example a
`port-forward` or Vite. Find the listener with `netstat -ano | findstr :8081` and stop that
PID.

## AWS (Terraform + EKS)

### `terraform apply`: `FreeTierRestrictionError: The specified backup retention period exceeds the maximum available to free tier customers`

Free-plan accounts may keep RDS backups for at most 1 day. `db_backup_retention_days`
defaults to 1 for that reason. On a Paid plan, set 7 in `terraform/terraform.tfvars`.
Everything else created before the error stays; fix the value and apply again.

### EC2 or node group launch fails on a Free-plan account

Free-plan accounts can only launch Free-plan-eligible instance types. List them with
`aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true`. In Sydney
these are t3/t4g/t8i micro and small, `c7i-flex.large` and `m7i-flex.large`. A dry run
(`--dry-run`) only checks IAM permissions, so it doesn't catch this.

### Ingress Service stays `<pending>`: `OperationNotPermitted: This AWS account currently does not support creating load balancers`

AWS hasn't cleared this (new) account for Elastic Load Balancing. You have two options:

- **Without a load balancer:** run `INGRESS_MODE=port-forward scripts/eks-deploy.sh` and
  open the app with `kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80`
  (http://medicloud.localhost:8081).
- **To get one:** open a free **Account and billing** case with AWS Support asking for
  Elastic Load Balancing in ap-southeast-2.

### `aws ssm get-parameter --name /aws/...` says `ParameterNotFound` in Git Bash

Git Bash rewrites arguments that start with `/` into Windows paths. Prefix the command with
`MSYS_NO_PATHCONV=1`.

### `AccessDenied` / `AccessDeniedException` from Terraform or the AWS CLI

The CLI user needs rights to create IAM roles, EKS, RDS, ECR, KMS, Secrets Manager,
CloudWatch Logs and EC2. Creating IAM roles for EKS is admin-equivalent anyway, so this
project uses `AdministratorAccess` on the operator's own user. Check who you are with
`aws sts get-caller-identity`.

### CD: `Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity`

The token's subject doesn't match the deploy role's trust policy. Look up the subject GitHub
actually sent:

```bash
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity   --max-results 1 --query "Events[0].CloudTrailEvent" --output text
```

- `userName` is `repo:<owner>@<id>/<repo>@<id>:environment:production`: the repository
  uses immutable IDs. Set `github_owner_id` and `github_repository_id` in
  `terraform/terraform.tfvars` (values from `https://api.github.com/repos/<owner>/<repo>`) and
  apply. This is a free, in-place IAM update (D49).
- The job has no `:environment:production`: the job isn't running in the `production`
  Environment.
- No CloudTrail event at all: check the `AWS_ROLE_ARN` secret.

### CD job is skipped

The repository variable must be named exactly `DEPLOY_ENABLED` with the value `true`, under
**Settings → Secrets and variables → Actions → Variables → Repository variables** (not an
Environment variable and not a Secret). After fixing it, use **Re-run all jobs** or
**Run workflow**.

## Ansible

### Docker fails to start on the EC2 server: `no sockets found via socket activation`

A docker-ce install can reload `docker.socket` while it is running. That leaves the socket
with no listening descriptor, and repeated retries then hit systemd's start limit. The
`docker` role starts `docker.socket` before `docker.service`, and if that fails it runs
`systemctl reset-failed` and recreates the socket. To fix it by hand on the server:
`sudo systemctl reset-failed docker.socket docker.service && sudo systemctl restart docker.socket && sudo systemctl start docker`.

### SSH times out from campus or other restricted Wi-Fi

Two possible causes:

- **Your public IP changed.** Run `scripts/app-host-access.sh`, then
  `terraform -chdir=terraform apply` (only the SSH rule changes).
- **The network blocks outbound port 22.** sshd also listens on 443, so add
  `-e ansible_port=443` to the Ansible command.

### Ansible ignores `ansible.cfg`, or tries to execute the vault password file

Windows bind mounts show up world-writable and executable inside containers. Ansible then
ignores an `ansible.cfg` in the current directory, and runs an "executable" vault password
file as a script. `ansible/run.sh` avoids both:

- it sets `ANSIBLE_CONFIG` explicitly;
- it keeps the SSH key and vault password in the `medicloud-ansible-secrets` Docker volume.

### `No image in ECR yet` from the playbook

The playbook deploys the newest image in ECR. ECR is recreated every session, so push images
first with `INGRESS_MODE=port-forward scripts/eks-deploy.sh` (or the CD pipeline), or pass
`-e image_tag=<tag>`.

## EKS networking and monitoring

### A NetworkPolicy doesn't stop existing traffic

On EKS, the VPC CNI network-policy agent blocks **new** connections. Connections that were
already established (such as pooled database connections) keep working. To test an outage
for real, also end the existing sessions. For the database experiment, run a short-lived
psql pod (it isn't covered by the chaos policy) that executes:

```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE usename = current_user AND pid <> pg_backend_pid() AND backend_type = 'client backend';
```

### After deleting an egress NetworkPolicy, pods can't resolve DNS

This was observed with VPC CNI v1.22: after `chaos-block-database.yaml` was deleted, the
backend pods kept failing DNS lookups (`Temporary failure in name resolution`) for more than
5 minutes. Restarting them fixes it:
`kubectl rollout restart deployment/backend -n medicloud`. New pods are Ready in about
20 seconds.

### A Grafana stat shows "No data" instead of 0

Series that never occurred don't exist. For example, pods that never returned a 5xx have no
5xx series, so the ratio query returns nothing. Write the query as `(... or vector(0))`, as
the `medicloud:http_errors:ratio5m` recording rule does.

### `kubectl port-forward`: `unable to listen on any of the requested ports` / `lost connection to pod`

There are two separate messages:

- **`unable to listen`:** another port-forward still holds the port. Stop it first.
- **`lost connection to pod`:** the pod behind the forward was replaced, for example after a
  config change or rollout. Start the port-forward again.
