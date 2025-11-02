"""
Cryptography utilities for secret encryption and decryption.

Provides AES-256 encryption with PBKDF2 key derivation.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


def encrypt_secret(secret_value: str, password: str) -> str:
    """
    Encrypt a secret using AES-256 with a password.
    
    Args:
        secret_value: The secret to encrypt
        password: The password to use for encryption
        
    Returns:
        str: Base64-encoded encrypted secret with salt and IV prepended
    """
    # Generate a random salt for PBKDF2
    salt = os.urandom(16)
    
    # Derive a 256-bit key from the password using PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())
    
    # Generate a random 128-bit IV
    iv = os.urandom(16)
    
    # Create cipher and encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad the secret to be a multiple of 16 bytes (AES block size)
    secret_bytes = secret_value.encode()
    padding_length = 16 - (len(secret_bytes) % 16)
    padded_secret = secret_bytes + bytes([padding_length] * padding_length)
    
    # Encrypt the padded secret
    encrypted = encryptor.update(padded_secret) + encryptor.finalize()
    
    # Prepend salt and IV to encrypted data and encode as base64
    return base64.b64encode(salt + iv + encrypted).decode()


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted.
    
    This function checks if a value has the expected format of an encrypted secret:
    - Valid base64 encoding
    - Minimum length (salt + IV + at least one block = 48 bytes)
    
    Args:
        value: The value to check
        
    Returns:
        bool: True if the value appears to be encrypted, False otherwise
    """
    try:
        # Try to decode as base64
        decoded_data = base64.b64decode(value.encode())
        
        # Check minimum length (16 bytes salt + 16 bytes IV + 16 bytes minimum ciphertext)
        if len(decoded_data) < 48:
            return False
        
        # Check that the length is at least reasonable for encrypted data
        # Encrypted data should have salt (16) + IV (16) + ciphertext (multiple of 16)
        if (len(decoded_data) - 32) % 16 != 0:
            return False
        
        return True
    except Exception:
        # If base64 decoding fails or any other error, it's not encrypted
        return False


def decrypt_secret(encrypted_value: str, password: str) -> str:
    """
    Decrypt a secret using AES-256 with a password.
    
    Args:
        encrypted_value: Base64-encoded encrypted secret with salt and IV prepended
        password: The password to use for decryption
        
    Returns:
        str: Decrypted secret
        
    Raises:
        ValueError: If decryption fails (wrong password or corrupted data)
    """
    try:
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_value.encode())
        
        # Validate minimum length (salt + IV + at least one block)
        if len(encrypted_data) < 48:  # 16 bytes salt + 16 bytes IV + 16 bytes minimum ciphertext
            raise ValueError("Invalid encrypted data - too short")
        
        # Extract salt (first 16 bytes), IV (next 16 bytes), and ciphertext
        salt = encrypted_data[:16]
        iv = encrypted_data[16:32]
        ciphertext = encrypted_data[32:]
        
        # Derive the same 256-bit key from the password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        
        # Create cipher and decrypt
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # Decrypt
        padded_secret = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Validate decrypted data is not empty
        if not padded_secret:
            raise ValueError("Empty decrypted data")
        
        # Validate and remove padding
        padding_length = padded_secret[-1]
        
        # Validate padding (PKCS7)
        if padding_length > 16 or padding_length == 0:
            raise ValueError("Invalid padding - likely wrong password")
        
        # Check that all padding bytes are the same
        for i in range(padding_length):
            if padded_secret[-(i+1)] != padding_length:
                raise ValueError("Invalid padding - likely wrong password")
        
        secret_bytes = padded_secret[:-padding_length]
        
        # Attempt to decode as UTF-8 to further validate
        return secret_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError("Decryption failed. Invalid password or corrupted data")
    except Exception as e:
        raise ValueError(f"Decryption failed. Invalid password or corrupted data: {str(e)}")
