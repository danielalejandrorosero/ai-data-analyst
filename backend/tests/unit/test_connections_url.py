from app.domain.datasets.connections import _postgres_url
from app.domain.datasets.schemas import ExternalConnectionCreateRequest


def _payload(**overrides) -> ExternalConnectionCreateRequest:
    defaults = {
        "type": "postgres",
        "name": "x",
        "host": "example.com",
        "port": 5432,
        "database_name": "mydb",
        "username": "myuser",
        "password": "irrelevant",
    }
    defaults.update(overrides)
    return ExternalConnectionCreateRequest(**defaults)


class TestPostgresUrlEscaping:
    def test_password_containing_at_sign_does_not_corrupt_the_host(self):
        """Regresion: un f-string manual interpolando username/password sin
        escapar hacia que un "@" en la password se confundiera con el
        separador userinfo/host, corrompiendo el host de destino - un vector
        real de SSRF-smuggling si en el futuro se agrega un allowlist solo
        sobre el campo `host`."""
        url = _postgres_url(_payload(password="S3cr3t@Pass"))

        assert url.host == "example.com"
        assert url.username == "myuser"
        assert url.password == "S3cr3t@Pass"
        assert url.port == 5432
        assert url.database == "mydb"

    def test_password_containing_slash_and_colon_does_not_break_parsing(self):
        url = _postgres_url(_payload(password="p:a/s#s?word"))

        assert url.host == "example.com"
        assert url.password == "p:a/s#s?word"

    def test_username_containing_special_characters(self):
        url = _postgres_url(_payload(username="user@domain", password="x"))

        assert url.username == "user@domain"
        assert url.host == "example.com"
