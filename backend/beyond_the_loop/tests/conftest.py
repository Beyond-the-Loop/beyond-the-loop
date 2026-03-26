import pytest


# Run all anyio-based async tests only with asyncio (trio is not installed).
@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param
