# Air-Gapped Patching & Update Procedure — Project 117

**Document Version:** 1.0  
**Target Environment:** Isolated Air-Gapped Industrial Plant Networks

---

## 1. Overview

In air-gapped refinery environments, Project 117 instances have **no outbound or inbound internet connectivity**. All software updates, security patches, updated model weights, and document updates must follow a secure, cryptographically verified offline transfer procedure.

---

## 2. Update Package Preparation (Secure Build Station)

On an internet-connected, authenticated build machine:

1. **Bundle Wheel Packages & Dependencies:**
   ```bash
   uv pip compile pyproject.toml -o update_requirements.txt
   uv pip download -r update_requirements.txt -d ./wheels/
   ```

2. **Generate Manifest & Cryptographic Signatures:**
   ```bash
   sha256sum wheels/* > update_manifest.sha256
   # Sign the manifest with release authority Ed25519 key
   python scripts/sign_release_manifest.py update_manifest.sha256
   ```

3. **Burn to Secure Media:**
   Write the signed update archive to write-once optical media (CD-R/DVD-R) or hardware-encrypted, audited USB drive.

---

## 3. Plant Ingestion & Verification (Air-Gapped Host)

1. **Mount Media & Copy Archive:**
   ```bash
   cp /media/update_bundle/p117-update-*.tar.gz /opt/p117/updates/
   cd /opt/p117/updates/
   tar -xzf p117-update-*.tar.gz
   ```

2. **Verify Manifest & Signatures Before Execution:**
   ```bash
   # 1. Verify sha256 checksums of all wheels
   sha256sum -c update_manifest.sha256
   # 2. Verify release signature
   python3 scripts/verify_artifact_standalone.py update_manifest.sha256
   ```

3. **Apply Python Wheel Updates:**
   ```bash
   uv pip install --no-index --find-links ./wheels/ -r update_requirements.txt
   ```

4. **Run Pre-Flight Self-Audits & Verification Suite:**
   ```bash
   uv run pytest tests/unit/ tests/materials/ -q
   python3 scripts/verify_audit_chain.py data/project117.db
   ```

5. **Restart System Services:**
   ```bash
   sudo systemctl restart p117-backend
   sudo systemctl restart p117-egress
   ```

---

## 4. Rollback Procedure

In case of post-patch anomalies:
1. Stop backend: `sudo systemctl stop p117-backend`
2. Restore database from pre-patch snapshot: `cp data/project117.db.bak data/project117.db`
3. Rollback virtualenv to previous wheel cache: `uv pip install --no-index --find-links /opt/p117/wheels-previous/ -r previous_requirements.txt`
4. Restart service: `sudo systemctl start p117-backend`
