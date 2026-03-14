"""
Credential encryption/decryption for the Discord Twitter Bot.
Matches the web portal's AES-256-GCM encryption scheme.
"""

import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

IV_LENGTH = 12  # 96 bits for AES-GCM


def _get_key() -> bytes:
    """Derive a 256-bit AES key from the ENCRYPTION_KEY env var using PBKDF2."""
    secret = os.getenv('ENCRYPTION_KEY')
    if not secret:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")

    # Match the web portal's PBKDF2 derivation
    key = hashlib.pbkdf2_hmac(
        'sha256',
        secret.encode('utf-8'),
        b'nexus-twitter-bot-salt',
        100000,
        dklen=32
    )
    return key


def decrypt(encrypted_base64: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext."""
    key = _get_key()
    combined = base64.b64decode(encrypted_base64)

    iv = combined[:IV_LENGTH]
    ciphertext = combined[IV_LENGTH:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode('utf-8')


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext using AES-256-GCM. Returns base64-encoded IV+ciphertext."""
    key = _get_key()
    iv = os.urandom(IV_LENGTH)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)

    combined = iv + ciphertext
    return base64.b64encode(combined).decode('utf-8')
