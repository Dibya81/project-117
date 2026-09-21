# Out-of-Scope Security Considerations — Project 117

**Document Version:** 1.0  
**Classification:** INTERNAL / SECURITY ARCHITECTURE  
**Target Environment:** Edge Industrial Control Systems

---

## 1. Purpose

This document explicitly defines the threat boundaries and attack scenarios that Project 117 **does not** claim to protect against. Establishing explicit boundaries prevents false assumptions regarding system resilience.

---

## 2. Explicitly Out-of-Scope Threats

### 2.1 Physical Host Hardware Compromise
- **Out of Scope:** An attacker with physical access to the server motherboard, memory buses, or storage controllers (e.g. cold-boot attacks, PCIe DMA interposers, hardware keyloggers).
- **Assumption:** The host server is located inside a physically secured plant control room with badge access and physical surveillance.

### 2.2 Host Operating System / Kernel Zero-Days
- **Out of Scope:** Kernel-level privilege escalations or hypervisor escapes that compromise the host root account.
- **Assumption:** Host OS hardening, SELinux policies, and kernel patching are managed by plant IT/OT infrastructure teams.

### 2.3 Malicious Model Weight Supply Chain (Trojaned Weights)
- **Out of Scope:** Upstream backdoors embedded in base model weights (e.g., Qwen, Llama, Mistral) during training.
- **Assumption:** Model weights are obtained from verified sources and checked against cryptographic hashes prior to air-gapped staging.

### 2.4 Analog Sensor Wire Spoofing (Pre-Digitization)
- **Out of Scope:** Physical wiretaps or signal generators attached directly to analog 4-20mA sensor loops or thermocouples prior to RTU/PLC sampling.
- **Mitigation at other layers:** Multi-sensor cross-correlation and anomaly detection help flag discordant readings, but hardware wire security belongs to the plant physical security domain.

### 2.5 Denial of Service from Power or Cooling Failure
- **Out of Scope:** Facility-level electrical outages, HVAC cooling failures, or deliberate physical sabotage of cabling.
- **Assumption:** Plant UPS and backup generators provide power resilience for critical control racks.
