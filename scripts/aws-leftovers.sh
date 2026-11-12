#!/usr/bin/env bash
# READ-ONLY check for anything MediCloud could still be billing you for.
#
#   scripts/aws-leftovers.sh [region]      (default ap-southeast-2)
#
# Exit code 0 = nothing billable found, 1 = something needs attention.
set -uo pipefail
REGION="${1:-ap-southeast-2}"
found=0

check() { # check "<label>" <aws cli args...>   (prints the result if non-empty)
  local label="$1"; shift
  local out
  out=$(aws "$@" --region "$REGION" --output text 2>/dev/null | sed '/^None$/d;/^$/d')
  if [ -n "$out" ]; then
    echo "  [!] ${label}:"
    while IFS= read -r line; do echo "        $line"; done <<<"$out"
    found=1
  else
    echo "  [ok] ${label}: none"
  fi
}

echo "Billable leftovers in ${REGION}:"
check "EKS clusters"            eks list-clusters --query 'clusters[]'
# shellcheck disable=SC2016  # backticks are a JMESPath literal for the AWS CLI, not shell
check "Running EC2 instances"   ec2 describe-instances --filters Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].[InstanceId,InstanceType,Tags[?Key==`Name`]|[0].Value]'
check "NAT gateways"            ec2 describe-nat-gateways --filter Name=state,Values=pending,available --query 'NatGateways[].[NatGatewayId,VpcId]'
check "Load balancers (v2)"     elbv2 describe-load-balancers --query 'LoadBalancers[].[LoadBalancerName,Type,State.Code]'
check "Classic load balancers"  elb describe-load-balancers --query 'LoadBalancerDescriptions[].LoadBalancerName'
check "RDS instances"           rds describe-db-instances --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceStatus]'
check "RDS manual snapshots"    rds describe-db-snapshots --snapshot-type manual --query 'DBSnapshots[].DBSnapshotIdentifier'
check "Elastic IPs"             ec2 describe-addresses --query 'Addresses[].[PublicIp,AssociationId]'
check "Unattached EBS volumes"  ec2 describe-volumes --filters Name=status,Values=available --query 'Volumes[].[VolumeId,Size]'

echo
echo "Resources still tagged Project=medicloud (may include free items such as IAM/ECR;"
echo "AWS's tagging index can also list resources deleted in the last hour or so):"
aws resourcegroupstaggingapi get-resources --region "$REGION" \
  --tag-filters Key=Project,Values=medicloud --query 'ResourceTagMappingList[].ResourceARN' \
  --output text 2>/dev/null | tr '\t' '\n' | sed '/^$/d;s/^/        /' || true

echo
if [ "$found" -eq 0 ]; then
  echo "RESULT: nothing billable found."
else
  echo "RESULT: billable resources remain - review the [!] lines above."
fi
exit "$found"
