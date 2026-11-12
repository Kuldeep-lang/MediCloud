#!/usr/bin/env bash
# Deploy MediCloud to the EKS cluster created by Terraform (manual equivalent of the CD
# pipeline in Phase 7). Run from Git Bash / Linux / macOS after `terraform apply`:
#
#   scripts/eks-deploy.sh
#
# Steps: kubeconfig -> ingress controller -> namespace -> build + push images to ECR
#        -> Secret from AWS Secrets Manager -> render EKS overlay -> apply -> smoke test.
# Requires: aws, kubectl, docker, python, terraform (all read from the Terraform outputs).
#
# INGRESS_MODE=nlb (default)   public AWS Network Load Balancer in front of the ingress.
# INGRESS_MODE=port-forward    no load balancer, for accounts AWS hasn't cleared to create
#                              one yet ("OperationNotPermitted"). Reach the app with
#                                kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80
#                              and open http://medicloud.localhost:8081
set -euo pipefail
cd "$(dirname "$0")/.."
INGRESS_MODE="${INGRESS_MODE:-nlb}"
LOCAL_HOST=medicloud.localhost

tf() { terraform -chdir=terraform output -raw "$1"; }
REGION=$(tf aws_region)
CLUSTER=$(tf cluster_name)
RDS_ENDPOINT=$(tf rds_endpoint)
SECRET_ARN=$(tf rds_master_secret_arn)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
# ECR tags are immutable: use the commit SHA, or a timestamp if there is no commit yet.
IMAGE_TAG=$(git rev-parse --short=12 HEAD 2>/dev/null || date +manual-%Y%m%d%H%M%S)
DEMO_PASSWORD="${SEED_DEMO_PASSWORD:-Demo@12345}"

echo "==> 1/7 kubeconfig for ${CLUSTER} (${REGION})"
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER" >/dev/null
kubectl get nodes

if [ "$INGRESS_MODE" = nlb ]; then
  echo "==> 2/7 ingress controller behind an AWS NLB"
  kubectl apply -k k8s/ingress-controller/eks
  kubectl rollout status deployment/nginx-ingress -n nginx-ingress --timeout=180s
  HOST=""
  for _ in $(seq 1 60); do
    HOST=$(kubectl get svc nginx-ingress -n nginx-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' || true)
    [ -n "$HOST" ] && break
    if kubectl get events -n nginx-ingress --field-selector involvedObject.name=nginx-ingress,reason=SyncLoadBalancerFailed \
         -o jsonpath='{.items[*].message}' 2>/dev/null | grep -q OperationNotPermitted; then
      echo "AWS refused to create the load balancer: this account is not yet allowed to create one."
      echo "Open an 'Account and billing' case with AWS Support, and meanwhile re-run with:"
      echo "  INGRESS_MODE=port-forward scripts/eks-deploy.sh"
      exit 1
    fi
    sleep 5
  done
  [ -n "$HOST" ] || { echo "NLB hostname not assigned"; exit 1; }
  echo "    NLB: $HOST"
else
  echo "==> 2/7 ingress controller without a load balancer (INGRESS_MODE=$INGRESS_MODE)"
  kubectl apply -k k8s/ingress-controller   # NodePort Service: no AWS load balancer
  kubectl rollout status deployment/nginx-ingress -n nginx-ingress --timeout=180s
  HOST="$LOCAL_HOST"
fi

echo "==> 3/7 namespace (Pod Security: restricted)"
kubectl apply -f k8s/00-namespace.yaml

echo "==> 4/7 build and push images (${IMAGE_TAG})"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
GIT_COMMIT="$IMAGE_TAG" docker compose build   # shown as the build version in the app
for app in backend frontend; do
  docker tag "medicloud-${app}:local" "${REGISTRY}/medicloud-${app}:${IMAGE_TAG}"
  docker push "${REGISTRY}/medicloud-${app}:${IMAGE_TAG}"
done

echo "==> 5/7 Secret from AWS Secrets Manager (password never written to disk)"
if ! kubectl get secret medicloud-secrets -n medicloud >/dev/null 2>&1; then
  SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --region "$REGION" --query SecretString --output text)
  DB_USER=$(python -c 'import json,sys; print(json.loads(sys.argv[1])["username"])' "$SECRET_JSON")
  DB_PASS=$(python -c 'import json,sys; print(json.loads(sys.argv[1])["password"])' "$SECRET_JSON")
  JWT=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
  kubectl create secret generic medicloud-secrets -n medicloud \
    --from-literal=POSTGRES_USER="$DB_USER" \
    --from-literal=POSTGRES_PASSWORD="$DB_PASS" \
    --from-literal=JWT_SECRET_KEY="$JWT" \
    --from-literal=SEED_DEMO_PASSWORD="$DEMO_PASSWORD"
  unset SECRET_JSON DB_PASS JWT
else
  echo "    medicloud-secrets already exists - keeping it"
fi

echo "==> 6/7 render the EKS overlay and apply"
kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/eks \
  | sed -e "s|ACCOUNT_ID|${ACCOUNT_ID}|g" -e "s|IMAGE_TAG|${IMAGE_TAG}|g" \
        -e "s|RDS_ENDPOINT|${RDS_ENDPOINT}|g" -e "s|INGRESS_HOST|${HOST}|g" \
  | kubectl apply -f -
kubectl rollout status deployment/backend -n medicloud --timeout=600s
kubectl rollout status deployment/frontend -n medicloud --timeout=300s

if [ "$INGRESS_MODE" = nlb ]; then
  echo "==> 7/7 smoke test through the NLB"
  BASE="http://${HOST}"
else
  echo "==> 7/7 smoke test through a kubectl port-forward"
  kubectl port-forward -n nginx-ingress svc/nginx-ingress 18081:80 >/dev/null 2>&1 &
  PF_PID=$!
  trap 'kill "$PF_PID" 2>/dev/null || true' EXIT
  BASE="http://127.0.0.1:18081"
fi
code=000
for _ in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: ${HOST}" "${BASE}/api/v1/system/info" || true)
  [ "$code" = 200 ] && break
  sleep 10 # NLB target registration + DNS propagation take a minute or two
done
echo "    GET /api/v1/system/info -> ${code}"
[ "$code" = 200 ] || { echo "Smoke test failed"; exit 1; }
echo
if [ "$INGRESS_MODE" = nlb ]; then
  echo "MediCloud is live at:  http://${HOST}"
else
  echo "MediCloud is running on EKS. To open it:"
  echo "  kubectl port-forward -n nginx-ingress svc/nginx-ingress 8081:80"
  echo "  then browse to http://${LOCAL_HOST}:8081"
fi
echo "Tear down (stops all charges):  scripts/aws-teardown.sh"
