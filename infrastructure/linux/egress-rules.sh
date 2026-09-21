#!/usr/bin/env bash
# ==============================================================================
# Project 117 — Host-Level Egress Firewall (nftables)
#
# Enforces sovereign default-deny outbound network policy on deployment nodes.
# Only localhost (127.0.0.0/8, ::1) and optional operator LAN subnet are permitted.
# ==============================================================================

set -euo pipefail

LAN_SUBNET="${P117_LAN_SUBNET:-192.168.1.0/24}"
P117_USER="${P117_USER:-project117}"

echo "[*] Configuring nftables for Project 117 host egress lock..."

if ! command -v nft >/dev/null 2>&1; then
    echo "[-] nft command not found. Falling back to iptables if available..."
    if command -v iptables >/dev/null 2>&1; then
        iptables -F OUTPUT
        iptables -P OUTPUT DROP
        iptables -A OUTPUT -o lo -j ACCEPT
        iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
        if [ -n "$LAN_SUBNET" ]; then
            iptables -A OUTPUT -d "$LAN_SUBNET" -j ACCEPT
        fi
        echo "[+] iptables default-deny rules applied."
        exit 0
    else
        echo "[!] Error: Neither nftables nor iptables is installed on this host."
        exit 1
    fi
fi

# Apply clean nftables ruleset
nft flush ruleset

nft -f - <<EOF
table inet project117_egress {
    chain inbound {
        type filter hook input priority filter; policy accept;
        iif "lo" accept
        ct state established,related accept
    }

    chain outbound {
        type filter hook output priority filter; policy drop;
        oif "lo" accept
        ct state established,related accept
        ip daddr $LAN_SUBNET accept
    }
}
EOF

echo "[+] nftables sovereign egress filter active. External WAN traffic is blocked."
