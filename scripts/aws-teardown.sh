#!/usr/bin/env bash
# Remove MediCloud from AWS in the only safe order, then prove nothing billable is left.
#
#   scripts/aws-teardown.sh
#
# Why the order matters: the ingress controller's Service created a Network Load Balancer
# that Terraform does not know about. If `terraform destroy` runs first, the NLB (and its
# network interfaces) keeps billing and blocks deletion of the subnets and VPC.
set -euo pipefail
cd "$(dirname "$0")/.."

tf() { terraform -chdir=terraform output -raw "$1" 2>/dev/null || true; }
REGION=$(tf aws_region); REGION=${REGION:-ap-southeast-2}
CLUSTER=$(tf cluster_name)
VPC_ID=$(tf vpc_id)

if [ -n "$CLUSTER" ] && aws eks describe-cluster --name "$CLUSTER" --region "$REGION" >/dev/null 2>&1; then
  echo "==> 1/3 delete Kubernetes objects that own AWS resources"
  aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER" >/dev/null
  kubectl delete namespace medicloud medicloud-monitoring --ignore-not-found --timeout=5m || true
  # Same objects in both ingress modes (NLB or port-forward); deleting the Service
  # removes the NLB if there is one.
  kubectl delete -k k8s/ingress-controller/eks --ignore-not-found --timeout=5m || true

  if [ -n "$VPC_ID" ]; then
    echo "    waiting for the NLB in ${VPC_ID} to disappear..."
    for _ in $(seq 1 40); do
      n=$(aws elbv2 describe-load-balancers --region "$REGION" \
            --query "length(LoadBalancers[?VpcId=='${VPC_ID}'])" --output text)
      [ "$n" = "0" ] && { echo "    load balancers gone"; break; }
      sleep 10
    done
  fi
else
  echo "==> 1/3 no cluster found - skipping Kubernetes cleanup"
fi

echo "==> 2/3 terraform destroy (review the plan, then type 'yes')"
terraform -chdir=terraform destroy "$@"

echo "==> 3/3 leftover check"
scripts/aws-leftovers.sh "$REGION"
