"""
Cryptography utilities for secret encryption and decryption.

Uses ML-KEM-768 (CRYSTALS-Kyber, NIST PQC standard) for key encapsulation
combined with AES-256-GCM for authenticated symmetric encryption (KEM+AEAD).

Scheme:
  encrypt(plaintext, password):
    1. Derive a deterministic ML-KEM-768 keypair from password via HKDF-SHA3-256
    2. Encapsulate → (shared_key_32, kem_ciphertext_1088)
    3. Encrypt plaintext with AES-256-GCM(shared_key) → (nonce_12, tag_16, ciphertext)
    4. Encode: "PQC:" + base64(kem_ciphertext ‖ nonce ‖ tag ‖ aes_ciphertext)

  decrypt(blob, password):
    1. Detect format prefix ("PQC:" = new, else = legacy AES-CBC)
    2. Re-derive keypair from password (same HKDF seed → same sk)
    3. Decapsulate kem_ciphertext → shared_key
    4. Decrypt with AES-256-GCM(shared_key, nonce, tag)

Legacy AES-256-CBC blobs (no prefix) are still decryptable for backwards
compatibility but new secrets are always written in PQC format.
"""

import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# ── PQC imports ───────────────────────────────────────────────────────────────
try:
    from kyber_py.kyber import Kyber768
    _PQC_AVAILABLE = True
except ImportError:
    _PQC_AVAILABLE = False

# ── Format constants ──────────────────────────────────────────────────────────
_PQC_PREFIX       = "PQC:"
_KEM_CT_LEN       = 1088   # ML-KEM-768 ciphertext bytes
_NONCE_LEN        = 12     # AES-GCM nonce
_TAG_LEN          = 16     # AES-GCM tag
_MIN_PQC_BLOB_LEN = _KEM_CT_LEN + _NONCE_LEN + _TAG_LEN  # 1116 bytes minimum

# ── Legacy AES-CBC constants (for backwards-compat decryption) ───────────────
_AES_SALT_LEN  = 16
_AES_IV_LEN    = 16
_MIN_AES_BLOB  = _AES_SALT_LEN + _AES_IV_LEN + 16  # 48 bytes


def _derive_kem_seed(password: str) -> bytes:
    """Derive a 48-byte deterministic seed from a password for ML-KEM keypair generation."""
    hkdf = HKDF(
        algorithm=hashes.SHA3_256(),
        length=48,  # AES256_CTR_DRBG requires exactly 48 bytes
        salt=b"merabytes-pqc-kem-seed-v1",
        info=b"kyber768-keygen",
        backend=default_backend(),
    )
    return hkdf.derive(password.encode("utf-8"))


def _keygen_from_password(password: str):
    """Derive a deterministic ML-KEM-768 keypair from a password."""
    seed = _derive_kem_seed(password)
    # kyber_py accepts a 64-byte seed to make keygen deterministic
    Kyber768.set_drbg_seed(seed)
    return Kyber768.keygen()


def encrypt_secret(secret_value: str, password: str) -> str:
    """
    Encrypt a secret using ML-KEM-768 + AES-256-GCM (PQC).

    Args:
        secret_value: The plaintext secret to encrypt.
        password:     The password used to derive the KEM keypair.

    Returns:
        str: "PQC:" + base64(kem_ct ‖ nonce ‖ tag ‖ aes_ct)

    Raises:
        RuntimeError: If kyber_py is not installed.
    """
    if not _PQC_AVAILABLE:
        raise RuntimeError(
            "kyber-py is not installed. Run: pip install kyber-py"
        )

    # 1. Derive keypair from password
    pk, _sk = _keygen_from_password(password)

    # 2. KEM encapsulation → (32-byte shared key, 1088-byte ciphertext)
    shared_key, kem_ct = Kyber768.encaps(pk)

    # 3. AES-256-GCM encryption with the shared key
    nonce = os.urandom(_NONCE_LEN)
    aesgcm = AESGCM(shared_key)
    aes_ct_with_tag = aesgcm.encrypt(nonce, secret_value.encode("utf-8"), None)
    # AESGCM.encrypt returns ciphertext || tag (tag appended)
    aes_ct   = aes_ct_with_tag[:-_TAG_LEN]
    tag      = aes_ct_with_tag[-_TAG_LEN:]

    # 4. Encode: kem_ct ‖ nonce ‖ tag ‖ aes_ct
    blob = base64.b64encode(kem_ct + nonce + tag + aes_ct).decode("ascii")
    return _PQC_PREFIX + blob


def decrypt_secret(encrypted_value: str, password: str) -> str:
    """
    Decrypt a secret.  Handles both PQC (ML-KEM-768 + AES-GCM) and
    legacy AES-256-CBC formats.

    Args:
        encrypted_value: Output of encrypt_secret() or a legacy AES-CBC blob.
        password:        The password used during encryption.

    Returns:
        str: The decrypted plaintext.

    Raises:
        ValueError: Wrong password, corrupted data, or unsupported format.
    """
    if encrypted_value.startswith(_PQC_PREFIX):
        return _decrypt_pqc(encrypted_value[len(_PQC_PREFIX):], password)
    else:
        return _decrypt_legacy_aes(encrypted_value, password)


def _decrypt_pqc(b64_blob: str, password: str) -> str:
    """Decrypt a PQC-format blob (base64 portion, without the 'PQC:' prefix)."""
    if not _PQC_AVAILABLE:
        raise RuntimeError("kyber-py is not installed. Run: pip install kyber-py")

    try:
        raw = base64.b64decode(b64_blob.encode("ascii"))
    except Exception:
        raise ValueError("Invalid PQC blob: base64 decode failed")

    if len(raw) < _MIN_PQC_BLOB_LEN:
        raise ValueError(f"Invalid PQC blob: too short ({len(raw)} < {_MIN_PQC_BLOB_LEN})")

    # Split layout: kem_ct(1088) ‖ nonce(12) ‖ tag(16) ‖ aes_ct(?)
    kem_ct  = raw[:_KEM_CT_LEN]
    nonce   = raw[_KEM_CT_LEN : _KEM_CT_LEN + _NONCE_LEN]
    tag     = raw[_KEM_CT_LEN + _NONCE_LEN : _KEM_CT_LEN + _NONCE_LEN + _TAG_LEN]
    aes_ct  = raw[_KEM_CT_LEN + _NONCE_LEN + _TAG_LEN :]

    # Re-derive the same keypair from password
    _pk, sk = _keygen_from_password(password)

    # KEM decapsulation → shared key
    try:
        shared_key = Kyber768.decaps(sk, kem_ct)
    except Exception as e:
        raise ValueError(f"KEM decapsulation failed (wrong password?): {e}")

    # AES-256-GCM decryption
    aesgcm = AESGCM(shared_key)
    try:
        plaintext = aesgcm.decrypt(nonce, aes_ct + tag, None)
    except Exception:
        raise ValueError("AES-GCM decryption failed: wrong password or corrupted data")

    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Decrypted data is not valid UTF-8")


def _decrypt_legacy_aes(encrypted_value: str, password: str) -> str:
    """Decrypt a legacy AES-256-CBC blob (no 'PQC:' prefix). Backwards compat only."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    try:
        encrypted_data = base64.b64decode(encrypted_value.encode())
    except Exception:
        raise ValueError("Invalid legacy blob: base64 decode failed")

    if len(encrypted_data) < _MIN_AES_BLOB:
        raise ValueError("Invalid legacy encrypted data — too short")

    salt       = encrypted_data[:16]
    iv         = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode())

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    if not padded:
        raise ValueError("Empty decrypted data")

    padding_length = padded[-1]
    if padding_length > 16 or padding_length == 0:
        raise ValueError("Invalid padding — likely wrong password")
    for i in range(padding_length):
        if padded[-(i + 1)] != padding_length:
            raise ValueError("Invalid padding — likely wrong password")

    try:
        return padded[:-padding_length].decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Decryption failed: invalid password or corrupted data")


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be an encrypted secret (PQC or legacy AES).

    Returns:
        bool: True if the value looks like an encrypted blob.
    """
    if not isinstance(value, str):
        return False

    # New PQC format
    if value.startswith(_PQC_PREFIX):
        try:
            raw = base64.b64decode(value[len(_PQC_PREFIX):].encode("ascii"))
            return len(raw) >= _MIN_PQC_BLOB_LEN
        except Exception:
            return False

    # Legacy AES-CBC format
    try:
        decoded = base64.b64decode(value.encode())
        if len(decoded) < _MIN_AES_BLOB:
            return False
        return (len(decoded) - 32) % 16 == 0
    except Exception:
        return False
