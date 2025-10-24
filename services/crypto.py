"""Cryptographic utilities for encrypting/decrypting sensitive data.

This module provides AES-GCM encryption for agent bot tokens.
The encryption key is read from the AGENT_TOKEN_AES_KEY environment variable (base64 encoded).
"""

import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


def get_encryption_key() -> bytes:
    """Get the encryption key from environment variable.
    
    Returns:
        bytes: The decoded encryption key (16, 24, or 32 bytes for AES).
    
    Raises:
        ValueError: If key is not set or has invalid length.
    """
    key_b64 = os.getenv("AGENT_TOKEN_AES_KEY")
    if not key_b64:
        raise ValueError(
            "AGENT_TOKEN_AES_KEY environment variable is not set. "
            "Please set it to a base64-encoded 16/24/32 byte key."
        )
    
    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"Failed to decode AGENT_TOKEN_AES_KEY from base64: {e}")
    
    if len(key) not in (16, 24, 32):
        raise ValueError(
            f"Invalid key length: {len(key)} bytes. "
            "AES-GCM requires 16, 24, or 32 byte keys."
        )
    
    return key


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token using AES-GCM.
    
    Args:
        plaintext: The plaintext token to encrypt.
    
    Returns:
        str: Base64-encoded encrypted data (nonce + ciphertext + tag).
    
    Raises:
        ValueError: If encryption key is invalid.
    """
    if not plaintext:
        raise ValueError("Plaintext token cannot be empty")
    
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    
    # Generate a random 12-byte nonce
    nonce = os.urandom(12)
    
    # Encrypt the plaintext
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    
    # Combine nonce + ciphertext for storage
    encrypted_data = nonce + ciphertext
    
    # Return as base64 for easy storage
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_token(encrypted_b64: str) -> str:
    """Decrypt an encrypted token using AES-GCM.
    
    Args:
        encrypted_b64: Base64-encoded encrypted data (nonce + ciphertext + tag).
    
    Returns:
        str: The decrypted plaintext token.
    
    Raises:
        ValueError: If decryption fails or data is corrupted.
    """
    if not encrypted_b64:
        raise ValueError("Encrypted token cannot be empty")
    
    try:
        key = get_encryption_key()
        aesgcm = AESGCM(key)
        
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_b64)
        
        # Extract nonce (first 12 bytes) and ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Decrypt
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
        
    except InvalidTag:
        logging.error("Decryption failed: Invalid authentication tag")
        raise ValueError("Failed to decrypt token: authentication failed")
    except Exception as e:
        logging.error(f"Decryption failed: {e}")
        raise ValueError(f"Failed to decrypt token: {e}")
