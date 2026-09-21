# Sovereign At-Rest Encryption Architecture

This document defines the at-rest cryptographic posture for Project 117 across server nodes, embedded hosts, and field mobile devices.

---

## 1. Storage Architecture & Layers

Project 117 enforces a defense-in-depth at-rest encryption strategy:

| Component | Storage Type | Encryption Mechanism | Key Management |
| :--- | :--- | :--- | :--- |
| **Relational Database** | SQLite (`project117.db`) | Host LUKS2 (or SQLCipher v4) | dm-crypt kernel keyring |
| **Vector Store** | LanceDB (`/data/lancedb`) | Host LUKS2 filesystem | dm-crypt / TPM 2.0 |
| **Staged Uploads** | Filesystem (`/data/uploads`) | Host LUKS2 filesystem | dm-crypt / TPM 2.0 |
| **Artifact Deliverables** | Filesystem (`/data/artifacts`) | Host LUKS2 + Ed25519 payload signatures | HMAC / Private Key |
| **Mobile Client** | Room DB (`project117_mobile_encrypted.db`) | SQLCipher v4 AES-256-CBC | Android Keystore `MasterKey` (AES-256-GCM) |
| **Mobile Preferences** | Key-Value | `EncryptedSharedPreferences` (AES256-SIV/GCM) | Android Keystore |

---

## 2. Server Host: Setting Up LUKS2 Encrypted Volume

On Linux air-gapped server nodes, all `/data` mount points must reside on a LUKS2 volume:

```bash
# 1. Format partition with LUKS2 (AES-XTS-PLAIN64 512-bit)
cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 --hash sha512 /dev/sdb1

# 2. Open encrypted mapping
cryptsetup luksOpen /dev/sdb1 project117_encrypted_data

# 3. Format filesystem (ext4)
mkfs.ext4 -L p117_data /dev/mapper/project117_encrypted_data

# 4. Mount to persistent data directory
mkdir -p /mnt/encrypted_data/project117
mount /dev/mapper/project117_encrypted_data /mnt/encrypted_data/project117
```

---

## 3. Docker Compose Encrypted Storage Mounts

Deployments running under container orchestration use `docker-compose.encrypted.yml`, which binds the active container storage volumes directly to the unlocked LUKS2 directory `/mnt/encrypted_data/project117`.

```bash
docker compose -f docker-compose.encrypted.yml up -d
```

---

## 4. Mobile Client SQLCipher Key Lifecycle

1. Upon first app launch, `DatabaseKeyManager` checks `EncryptedSharedPreferences` (backed by the hardware-backed Android Keystore) for a 256-bit passphrase.
2. If absent, a cryptographically secure 256-bit random seed (`SecureRandom`) is generated and sealed inside the Keystore.
3. `DatabaseModule` injects `SupportFactory(passphrase)` into Room's `databaseBuilder`.
4. If an unauthenticated attacker extracts the raw `.db` file via ADB or physical flash dumping, all tables, indices, and WAL frames remain unreadable ciphertext.
