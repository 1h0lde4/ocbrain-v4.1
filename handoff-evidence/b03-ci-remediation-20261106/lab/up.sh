#!/usr/bin/env bash
# Start containerd + dockerd for THIS call only (the daemon does not reliably survive between tool calls).
SP=/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/docker-lab
rm -f /run/containerd/containerd.sock /run/containerd/containerd.sock.ttrpc /var/run/docker.sock
(nohup containerd > "$SP/containerd.log" 2>&1 &)
for i in $(seq 1 30); do python3 -I -c "import socket; s=socket.socket(socket.AF_UNIX); s.settimeout(1); s.connect('/run/containerd/containerd.sock')" 2>/dev/null && break; sleep 1; done
(nohup dockerd --data-root "$SP/data" > "$SP/dockerd.log" 2>&1 &)
for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 1; done
docker info >/dev/null 2>&1 || { echo "dockerd did not come up"; exit 1; }
