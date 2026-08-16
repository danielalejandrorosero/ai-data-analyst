import pytest
from app.core.crypto import SecretDecryptionError, decrypt_secret, encrypt_secret


class TestEnvelopeEncryption:
    def test_roundtrip(self):
        ciphertext = encrypt_secret("super-secret-password")
        assert ciphertext != "super-secret-password"
        assert decrypt_secret(ciphertext) == "super-secret-password"

    def test_ciphertext_never_contains_plaintext(self):
        secret = "correcthorsebattery"
        ciphertext = encrypt_secret(secret)
        assert secret not in ciphertext

    def test_corrupted_ciphertext_raises_decryption_error_not_generic_exception(self):
        with pytest.raises(SecretDecryptionError):
            decrypt_secret("esto-no-es-un-token-fernet-valido")
