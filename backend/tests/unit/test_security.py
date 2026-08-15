import uuid

import pytest
from app.domain.auth.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext_password(self):
        password = "correcthorsebattery"
        hashed = hash_password(password)
        assert hashed != password

    def test_verify_password_accepts_correct_password(self):
        password = "correcthorsebattery"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_rejects_wrong_password(self):
        hashed = hash_password("correcthorsebattery")
        assert verify_password("wrongpassword", hashed) is False


class TestJwt:
    def test_decode_returns_the_same_user_id_that_was_encoded(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        assert decode_access_token(token) == user_id

    def test_decode_rejects_garbage_token(self):
        with pytest.raises(InvalidTokenError):
            decode_access_token("esto-no-es-un-jwt")

    def test_decode_rejects_token_signed_with_different_key(self):
        import jwt as pyjwt

        bad_token = pyjwt.encode(
            {"sub": str(uuid.uuid4())}, "otra-clave-distinta", algorithm="HS256"
        )
        with pytest.raises(InvalidTokenError):
            decode_access_token(bad_token)
