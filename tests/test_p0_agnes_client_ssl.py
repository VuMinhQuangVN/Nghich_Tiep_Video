import ssl

import certifi

from config import _normalize_agnes_base_url
from engines.agnes_client import AgnesClient


class DummyKeys:
    async def acquire_key(self):
        return "test-key"


def test_agnes_base_url_is_canonical_v1():
    assert _normalize_agnes_base_url("https://apihub.agnes-ai.com") == "https://apihub.agnes-ai.com/v1"
    assert _normalize_agnes_base_url("https://apihub.agnes-ai.com/v1/") == "https://apihub.agnes-ai.com/v1"


def test_agnes_client_normalizes_root_url():
    client = AgnesClient(DummyKeys(), "https://apihub.agnes-ai.com")
    assert client._base_url == "https://apihub.agnes-ai.com/v1"
    assert client._root_url == "https://apihub.agnes-ai.com"


def test_agnes_ssl_context_uses_certifi_bundle():
    context = AgnesClient._ssl_context()
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.get_ca_certs()
    assert certifi.where().endswith("cacert.pem")
