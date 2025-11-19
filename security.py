import os
import hashlib
import random
from cryptography.fernet import Fernet

KEY_FILE = "secret.key"

def load_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

KEY = load_or_create_key()
CIPHER = Fernet(KEY)

def encrypt_data(text: str) -> str:
    if text is None:
        return None
    return CIPHER.encrypt(text.encode()).decode()

def decrypt_data(token: str) -> str:
    if token is None:
        return None
    return CIPHER.decrypt(token.encode()).decode()

def hash_data(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()

def mask_contact(contact: str) -> str:
    if not contact:
        return "XXX-XXX-XXXX"
    last4 = contact[-4:] if len(contact) >= 4 else contact
    return "XXX-XXX-" + last4

def mask_name(name: str) -> str:
    return "ANON_" + str(random.randint(1000, 9999))
