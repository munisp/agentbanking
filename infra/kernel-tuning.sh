#!/bin/bash
# ==============================================================================
# Linux Kernel Tuning for Millions of TPS
# Run on each host machine before starting services
# Target: 64+ vCPU, 256+ GB RAM, NVMe SSD
# ==============================================================================

set -euo pipefail

echo "=== 54Link Kernel Tuning for High-Throughput Financial Processing ==="

# ── Network Stack ────────────────────────────────────────────────────────────
# Increase TCP connection backlog
sysctl -w net.core.somaxconn=65535
sysctl -w net.core.netdev_max_backlog=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# TCP memory (min/default/max in pages)
sysctl -w net.ipv4.tcp_mem="786432 1048576 26777216"
sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"

# Reuse TIME_WAIT sockets (critical for high connection rates)
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.ipv4.tcp_fin_timeout=15
sysctl -w net.ipv4.tcp_keepalive_time=300
sysctl -w net.ipv4.tcp_keepalive_intvl=30
sysctl -w net.ipv4.tcp_keepalive_probes=3

# Ephemeral port range (more ports for outbound connections)
sysctl -w net.ipv4.ip_local_port_range="1024 65535"

# TCP Fast Open (reduce latency for recurring connections)
sysctl -w net.ipv4.tcp_fastopen=3

# TCP congestion control (BBR for better throughput)
modprobe tcp_bbr 2>/dev/null || true
sysctl -w net.ipv4.tcp_congestion_control=bbr 2>/dev/null || true
sysctl -w net.core.default_qdisc=fq 2>/dev/null || true

# ── File Descriptors ─────────────────────────────────────────────────────────
sysctl -w fs.file-max=2097152
sysctl -w fs.nr_open=2097152

# ── Disk I/O ─────────────────────────────────────────────────────────────────
# io_uring support (TigerBeetle, high-perf I/O)
sysctl -w fs.aio-max-nr=1048576

# Dirty page writeback (balance between write throughput and data safety)
sysctl -w vm.dirty_ratio=40
sysctl -w vm.dirty_background_ratio=10
sysctl -w vm.dirty_expire_centisecs=3000
sysctl -w vm.dirty_writeback_centisecs=500

# ── Memory ───────────────────────────────────────────────────────────────────
# Reduce swappiness (prefer RAM for databases)
sysctl -w vm.swappiness=1

# Overcommit (PostgreSQL requires this)
sysctl -w vm.overcommit_memory=2
sysctl -w vm.overcommit_ratio=95

# Transparent Huge Pages — disable for databases (TigerBeetle, PostgreSQL, Redis)
echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
echo never > /sys/kernel/mm/transparent_hugepage/defrag 2>/dev/null || true

# Reserve huge pages for PostgreSQL shared_buffers
sysctl -w vm.nr_hugepages=32768  # 64GB with 2MB pages

# ── NVMe SSD Optimization ───────────────────────────────────────────────────
for dev in /sys/block/nvme*; do
    if [ -d "$dev/queue" ]; then
        echo none > "$dev/queue/scheduler" 2>/dev/null || true
        echo 2048 > "$dev/queue/nr_requests" 2>/dev/null || true
        echo 2 > "$dev/queue/rq_affinity" 2>/dev/null || true
        echo 0 > "$dev/queue/add_random" 2>/dev/null || true
    fi
done

# ── Process Limits ───────────────────────────────────────────────────────────
# Set via /etc/security/limits.conf for persistence:
#   * soft nofile 1048576
#   * hard nofile 1048576
#   * soft nproc 65535
#   * hard nproc 65535
#   * soft memlock unlimited
#   * hard memlock unlimited

echo "=== Kernel tuning complete ==="
echo "Reboot recommended for full effect. Persist settings in /etc/sysctl.d/99-54link.conf"
