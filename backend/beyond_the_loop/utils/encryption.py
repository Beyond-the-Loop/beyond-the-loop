from cryptography.fernet import Fernet

from open_webui.env import DB_FIELD_ENCRYPTION_KEY

_cipher = Fernet(DB_FIELD_ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    return _cipher.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _cipher.decrypt(ciphertext.encode()).decode()
