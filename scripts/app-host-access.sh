#!/usr/bin/env bash
# Enable the Ansible-managed EC2 VM and allow SSH from the network you are on *right now*.
# Run it before `terraform apply`, and again whenever your public IP changes (e.g. after
# moving to campus Wi-Fi); the next apply only updates the security-group rules.
#
#   scripts/app-host-access.sh            # writes terraform/app-host.auto.tfvars
#   terraform -chdir=terraform apply      # (needs approval: creates/updates resources)
#
# If the network blocks outbound port 22, Ansible can use the 443 fallback:
#   ansible/run.sh playbook.yml --tags host -e ansible_port=443
set -euo pipefail
cd "$(dirname "$0")/.."

ip=$(curl -fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')
[[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo "Could not determine your public IPv4 (got: '$ip')"; exit 1; }

pubkey=$(ansible/run.sh pubkey | tr -d '\r')
[[ "$pubkey" == ssh-ed25519\ * ]] || { echo "No Ansible SSH key yet - run: ansible/run.sh init"; exit 1; }

cat > terraform/app-host.auto.tfvars <<EOF
# Written by scripts/app-host-access.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ). Git-ignored.
enable_app_host         = true
app_host_ssh_public_key = "${pubkey}"
app_host_ssh_cidrs      = ["${ip}/32"]
EOF
echo "SSH to the app host will be allowed from ${ip}/32 (ports 22 and 443)."
echo "Next: terraform -chdir=terraform plan   then apply (approval needed)."
