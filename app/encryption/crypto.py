import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_SIZE = 12  # 96-bit, standard for AES-GCM


def generate_key():
    return AESGCM.generate_key(bit_length=256)


def _master_key():
    return base64.b64decode(os.environ["ENCRYPTION_MASTER_KEY"])


def wrap_key(raw_key):
    """Encrypts a per-version AES key at rest with the master key."""
    aesgcm = AESGCM(_master_key())
    nonce = os.urandom(NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, raw_key, None)


def unwrap_key(wrapped_key):
    aesgcm = AESGCM(_master_key())
    nonce, ciphertext = wrapped_key[:NONCE_SIZE], wrapped_key[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_payload(plaintext, key):
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, plaintext, None)


def decrypt_payload(ciphertext, key):
    aesgcm = AESGCM(key)
    nonce, actual_ciphertext = ciphertext[:NONCE_SIZE], ciphertext[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, actual_ciphertext, None)
