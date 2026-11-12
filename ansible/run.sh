#!/usr/bin/env bash
# Runs Ansible from the control-node container (Ansible doesn't run natively on Windows).
#
#   ansible/run.sh init                        one-time: SSH key + vault password + vault file
#   ansible/run.sh pubkey                      print the SSH public key (input for Terraform)
#   ansible/run.sh lint                        syntax check + ansible-lint
#   ansible/run.sh inventory                   show the hosts EC2 reports right now
#   ansible/run.sh playbook.yml [args...]      ansible-playbook, e.g. --tags host
#
# Mounts: the repo at /work, your AWS CLI config read-only, and a named Docker volume
# (medicloud-ansible-secrets) holding the SSH key and vault password, so neither ever
# lands on the Windows filesystem.
set -euo pipefail
export MSYS_NO_PATHCONV=1

root=$(cd "$(dirname "$0")/.." && pwd)
aws_dir="$HOME/.aws"
if command -v cygpath >/dev/null 2>&1; then   # Git Bash: give Docker C:/... paths
  root=$(cygpath -m "$root")
  aws_dir=$(cygpath -m "$aws_dir")
fi
image=medicloud-ansible:local
docker build -q -t "$image" "$root/ansible" >/dev/null

tty=()
if [ -t 0 ] && [ -t 1 ]; then tty=(-t); fi

run() {
  docker run --rm -i "${tty[@]}" \
    -v "$root:/work" \
    -v medicloud-ansible-secrets:/home/ansible/.secrets \
    -v "$aws_dir:/home/ansible/.aws:ro" \
    -e SEED_DEMO_PASSWORD -e INGRESS_MODE \
    "$image" "$@"
}

case "${1:-}" in
  init)
    run bash -euc '
      cd /home/ansible/.secrets
      [ -f id_ed25519 ] || ssh-keygen -q -t ed25519 -N "" -C medicloud-ansible -f id_ed25519
      [ -f vault_pass ] || (umask 077; python3 -c "import secrets; print(secrets.token_urlsafe(32))" > vault_pass)
      vault=/work/ansible/group_vars/app_servers/vault.yml
      if [ ! -f "$vault" ]; then
        python3 - > /tmp/vault.yml <<EOF
import secrets
print("---")
print("vault_postgres_password: " + secrets.token_urlsafe(24))
print("vault_jwt_secret_key: " + secrets.token_urlsafe(48))
print("vault_seed_demo_password: Demo@12345")
EOF
        ansible-vault encrypt /tmp/vault.yml --output "$vault" && rm /tmp/vault.yml
        echo "Created encrypted $vault"
      fi
      echo "SSH key and vault password are in the medicloud-ansible-secrets volume."'
    ;;
  pubkey)
    run cat /home/ansible/.secrets/id_ed25519.pub
    ;;
  lint)
    run bash -euc 'ansible-playbook playbook.yml --syntax-check && ansible-lint'
    ;;
  inventory)
    run ansible-inventory --graph --vars
    ;;
  "")
    sed -n '2,10p' "$0"
    ;;
  *)
    run ansible-playbook "$@"
    ;;
esac
