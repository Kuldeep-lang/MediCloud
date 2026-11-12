# MediCloud — 15-Minute Demo Guide

A scripted walkthrough for presenting MediCloud. Each step shows the command, what the
audience sees, and the point it makes. All commands run from the repository root in Git
Bash.

> **Cost:** the AWS environment costs about $0.46/hour while it exists. Build it about
> 45 minutes before presenting (§1) and tear it down right after (§4).

---

## 1. Before you present (T-45 min)

Do this on the network you'll present from, such as campus Wi-Fi, so the SSH rule matches
your IP there.

```bash
docker info >/dev/null && echo "Docker OK"            # Docker Desktop must be running
aws sts get-caller-identity --query Arn --output text  # AWS CLI works

scripts/app-host-access.sh                             # SSH allowed from this network's IP
terraform -chdir=terraform init
terraform -chdir=terraform plan -out tfplan            # check it creates what you expect
terraform -chdir=terraform apply tfplan                # ~20 min
INGRESS_MODE=port-forward scripts/eks-deploy.sh        # ~8 min: images -> ECR, app -> EKS
INGRESS_MODE=port-forward ansible/run.sh playbook.yml  # ~10 min: EC2 server, EKS bootstrap, monitoring
```

If Ansible can't reach the server, the network probably blocks port 22. Add
`-e ansible_port=443` to the command.

Open these in separate terminals and keep them running:

```bash
kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80          # app on EKS
kubectl port-forward -n medicloud-monitoring svc/grafana 3000:3000       # Grafana
kubectl port-forward -n medicloud-monitoring svc/prometheus 9090:9090    # Prometheus
```

Open these browser tabs in advance:

| Tab | URL |
|---|---|
| App on EKS | http://medicloud.localhost:8081 (log in as `admin@medicloud.demo` / `Demo@12345`) |
| App on EC2 | `http://<app_host_public_ip>` (`terraform -chdir=terraform output -raw app_host_public_ip`) |
| Grafana | http://localhost:3000 (user `admin`; password from `kubectl get secret grafana-admin -n medicloud-monitoring -o jsonpath='{.data.admin-password}' \| base64 -d`) |
| Prometheus alerts | http://localhost:9090/alerts |
| GitHub Actions | your repository's **Actions** tab (once pushed) |

---

## 2. The demo (15 minutes)

### 0:00 — The problem and the app (2 min)

**Show:** the app on EKS. Walk through the dashboard, then Patients → a patient → book an
appointment, then Beds and Billing.

**Say:**

- "A working hospital system: patients, doctors, appointments, beds, pharmacy and billing.
  Every figure comes from PostgreSQL."
- "All data is synthetic and payments are simulated."
- "Four roles with server-side access control." To show it, log in as
  `doctor@medicloud.demo` and point out the smaller menu.

### 2:00 — Infrastructure as code (3 min)

**Show:** `terraform/` in the editor (modules), then:

```bash
terraform -chdir=terraform state list | wc -l        # ~60 resources, all from code
terraform -chdir=terraform plan                      # "No changes": no drift
```

**Say:**

- "Seven modules I wrote myself: VPC, security groups, IAM, EKS, ECR, RDS and the EC2
  server."
- "Each module has offline tests (`terraform test` with a mocked AWS) that assert the
  security properties. For example, the database is never public and its password lives
  only in Secrets Manager."
- "Prices were verified from AWS's price list. The environment is built per session and
  destroyed after, so a session costs about $2."

### 5:00 — Kubernetes on EKS (3 min)

**Show:**

```bash
kubectl get nodes
kubectl get pods,hpa -n medicloud
kubectl get networkpolicy -n medicloud
```

**Say:**

- "Two worker nodes in private subnets. Frontend and API run two replicas each, and the API
  autoscales from 2 to 6 on CPU."
- "Pods run as non-root with read-only filesystems, under the `restricted` Pod Security
  Standard."
- "Zero-trust networking: only the ingress can reach the app, and only the API can reach
  the database."
- "The database is Amazon RDS, private, and the connection is TLS 1.3."

Optional live action: `kubectl delete pod -n medicloud -l app.kubernetes.io/name=frontend`,
then `kubectl get pods -n medicloud -w`. "Kubernetes replaces it in seconds. The app stays
up because there are two replicas and a disruption budget."

### 8:00 — Configuration management with Ansible (2 min)

**Show:** the app on EC2, then:

```bash
ansible/run.sh inventory                        # hosts discovered from EC2 tags, no IPs in files
ansible/run.sh playbook.yml --tags host         # end of output: changed=0
```

**Say:**

- "The same images also run on a plain Ubuntu server. Ansible installs Docker from Docker's
  signed repository and a metrics agent, then deploys the app with secrets from an
  encrypted vault."
- "Running it again changes nothing. That's idempotency: the playbook describes the desired
  state."

### 10:00 — CI/CD (2 min)

**Show:** the GitHub Actions tab with a green CI run, and `.github/workflows/cd.yml`.

**Say:**

- "Every push runs tests against a real PostgreSQL, linters for all the infrastructure code,
  a secret scan, and vulnerability scans of both images. A fixable HIGH or CRITICAL CVE
  fails the build."
- "CD logs into AWS with short-lived OIDC credentials, so no keys are stored in GitHub. It
  pushes immutable images, rolls them out and smoke-tests them, and rolls back
  automatically if anything fails."
- "Every action is pinned to a commit hash, because of the 2026 supply-chain attack on
  Trivy's GitHub actions."

### 12:00 — Monitoring and a live failure (3 min)

**Show:** the Grafana **MediCloud Overview** dashboard: API health, latency percentiles,
Kubernetes resources, hospital gauges and the EC2 server.

Optional live failure (about 2 minutes, with recovery):

```bash
kubectl apply -f k8s/tools/chaos-block-database.yaml
# then end the API's existing DB sessions - command in docs/troubleshooting.md
#   ("A NetworkPolicy doesn't stop existing traffic")
```

**Say, while watching Grafana and the Prometheus alerts tab:**

- "Requests fail fast instead of hanging; I added database timeouts after the first
  experiment showed they could hang for 15 minutes."
- "Kubernetes pulls the unhealthy pods out of the Service. The `DatabaseDown` alert fires
  after a minute and names the real cause."

**Recover:**

```bash
kubectl delete -f k8s/tools/chaos-block-database.yaml
kubectl rollout restart deployment/backend -n medicloud
```

**Close:** "Everything you saw, from network and cluster to app and dashboards, came from
code in one repository, and I can destroy it all and rebuild it with the same commands."

---

## 3. Questions you may get

| Question | Short answer |
|---|---|
| Why is EKS reached through port-forward? | AWS hasn't yet allowed this new account to create load balancers. The code supports an NLB (`INGRESS_MODE=nlb`); the EC2 server shows a public deployment. |
| Why not Helm? | Hand-written manifests are explainable line by line and small enough for this cluster (decision D9). Helm is the upgrade path. |
| How are secrets handled? | They're never in git. The RDS password is generated by AWS in Secrets Manager. Kubernetes Secrets are created from it at deploy time, and Ansible uses an encrypted vault. CI uses OIDC instead of keys. |
| What would you change for production? | Multi-AZ RDS, a NAT gateway per AZ, TLS with a domain, Alertmanager, durable Prometheus storage, a least-privilege database user, and remote Terraform state (the bootstrap module exists). |
| What did you learn from testing? | Missing DB timeouts (fixed), Free-plan limits (instance types, backup retention, load balancers), and VPC CNI network-policy behaviour. The decision log (D38–D47) records each one. |

---

## 4. After you present (always)

```bash
scripts/aws-teardown.sh      # type "yes" at the prompt; ends with a leftover check
scripts/aws-leftovers.sh     # exit code 0 = nothing billable left
```

---

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| Ansible times out on SSH | Run `scripts/app-host-access.sh` and `terraform -chdir=terraform apply` (your IP changed), or add `-e ansible_port=443` (port 22 blocked) |
| http://medicloud.localhost:8081 doesn't load | Restart the port-forward (it drops when pods are replaced) |
| Grafana tile says "No data" right after a deploy | Wait 30 s for the first scrapes, then refresh |
| Pods can't resolve DNS after the failure demo | `kubectl rollout restart deployment/backend -n medicloud` |
| Anything else | [troubleshooting.md](troubleshooting.md). As a fallback, show the screenshots in your report. |
