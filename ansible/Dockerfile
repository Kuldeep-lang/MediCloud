# syntax=docker/dockerfile:1
# Ansible control node. Ansible doesn't run natively on Windows, so it runs here; CI uses
# the same image, so local and pipeline runs behave the same.
#
#   docker build -t medicloud-ansible:local ansible/
#   ansible/run.sh <ansible-playbook args>      (wrapper with the right mounts)
FROM python:3.13-slim

ARG KUBECTL_VERSION=v1.37.2
ARG KUBECTL_SHA256=c04487523e7aa7d1493f7808174c899db93d7a9cf57531420cd76b9bd415f8f4
ARG AWSCLI_VERSION=2.36.50

# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client ca-certificates curl unzip \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

# kubectl (checksum-verified) and AWS CLI v2 (EKS tokens, ECR, Secrets Manager).
RUN curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
 && echo "${KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum -c - \
 && chmod 0755 /usr/local/bin/kubectl \
 && curl -fsSLo /tmp/awscli.zip "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" \
 && unzip -q /tmp/awscli.zip -d /tmp \
 && /tmp/aws/install \
 && rm -rf /tmp/aws /tmp/awscli.zip

COPY requirements.txt requirements.yml /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && ansible-galaxy collection install -r /tmp/requirements.yml -p /usr/share/ansible/collections \
 && rm /tmp/requirements.txt /tmp/requirements.yml

# Non-root operator. SSH keys and the vault password live in a named volume mounted at
# ~/.secrets, never on the Windows filesystem (bind mounts there show up world-readable).
RUN useradd --create-home --uid 1000 ansible \
 && install -d -m 0700 -o ansible -g ansible /home/ansible/.secrets /home/ansible/.ssh
USER ansible
WORKDIR /work/ansible
ENV ANSIBLE_CONFIG=/work/ansible/ansible.cfg \
    ANSIBLE_FORCE_COLOR=1 \
    AWS_PAGER=""
ENTRYPOINT []
CMD ["ansible", "--version"]
