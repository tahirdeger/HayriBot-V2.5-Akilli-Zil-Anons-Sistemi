
from cryptography.fernet import Fernet
import base64
import os

class DataEncryptor:
    def __init__(self):
        self.key = base64.urlsafe_b64encode(os.urandom(32))
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()

# Kullanım örneği:
# encryptor = DataEncryptor()
# encrypted = encryptor.encrypt("sensitive_data")


