import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.core.cache import AsyncTTLCache
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.services.llm_service import (
    BaseLLMProvider,
    ClaudeProvider,
    GeminiProvider,
    LLMResponse,
    LLMService,
    OllamaProvider,
    get_provider_factory,
)


# ─────────────────────────────────────────────────────────────
# 1. Tests de Infraestructura: Rate Limiter & Memory Leak Cleanup
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_cleans_old_timestamps_and_prevents_memory_leak():
    """
    Verifica que el Rate Limiter limpie las marcas de tiempo que superen
    la ventana de 60 segundos, evitando el crecimiento indefinido de memoria.
    """
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=1.0)

    # 1. Consumir los 3 cupos
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is False  # 4to request es bloqueado
    assert limiter.current_count == 3

    # 2. Esperar a que la ventana de 1.0s expire
    await asyncio.sleep(1.1)

    # 3. Al invocar acquire() nuevamente, debe purgar los viejos y permitir el nuevo request
    assert await limiter.acquire() is True
    # La cola debe contener únicamente 1 elemento (el recién añadido), habiendo limpiado los 3 anteriores
    assert limiter.current_count == 1


# ─────────────────────────────────────────────────────────────
# 2. Tests de Validación Temprana (Fail-Fast)
# ─────────────────────────────────────────────────────────────

def test_provider_fail_fast_raises_value_error_on_missing_api_keys():
    """
    Verifica que si faltan las credenciales para el proveedor activo,
    se levante un ValueError descriptivo durante la inicialización.
    """
    with pytest.raises(ValueError, match="GEMINI_API_KEY no está definida"):
        GeminiProvider(api_key="", validate=True)

    with pytest.raises(ValueError, match="CLAUDE_API_KEY no está definida"):
        ClaudeProvider(api_key="", validate=True)

    with pytest.raises(ValueError, match="OLLAMA_BASE_URL no está definida"):
        OllamaProvider(base_url="", validate=True)

    with pytest.raises(ValueError, match="Proveedor LLM desconocido"):
        get_provider_factory("proveedor_invalido")


# ─────────────────────────────────────────────────────────────
# 3. Tests de Adaptadores de Proveedores (Mocks de Red)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gemini_provider_formats_payload_and_parses_response():
    """
    Verifica el formato del request y parseo de respuesta de Google Gemini.
    """
    provider = GeminiProvider(api_key="test_gemini_key", validate=False)

    fake_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Acción 1: Implementar DCIM."}]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        text = await provider.generate("Genera recomendaciones")

        assert text == "Acción 1: Implementar DCIM."
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "key=test_gemini_key" in args[0]
        assert "contents" in kwargs["json"]


@pytest.mark.asyncio
async def test_claude_provider_formats_headers_and_parses_response():
    """
    Verifica los headers x-api-key y estructura de Anthropic Claude.
    """
    provider = ClaudeProvider(api_key="test_claude_key", validate=False)

    fake_response = {
        "content": [
            {"type": "text", "text": "Acción 1: Reducir latencia con orquestación."}
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        text = await provider.generate("Prompt para Claude")

        assert text == "Acción 1: Reducir latencia con orquestación."
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["x-api-key"] == "test_claude_key"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"


@pytest.mark.asyncio
async def test_ollama_provider_payload_and_parsing():
    """
    Verifica la llamada local a Ollama REST API.
    """
    provider = OllamaProvider(base_url="http://localhost:11434", validate=False)

    fake_response = {"response": "Acción 1: Mejorar PUE a 1.2."}

    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        text = await provider.generate("Prompt para Ollama")

        assert text == "Acción 1: Mejorar PUE a 1.2."
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/generate"
        assert kwargs["json"]["model"] == "llama3"


# ─────────────────────────────────────────────────────────────
# 4. Tests de Orquestación: LLMService (Cache, Rate Limit, Fallbacks)
# ─────────────────────────────────────────────────────────────

class MockCustomProvider(BaseLLMProvider):
    name = "mock_provider"

    def __init__(self, return_text: str = "Respuesta Mock"):
        self.return_text = return_text
        self.call_count = 0

    def validate_credentials(self) -> None:
        pass

    async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
        self.call_count += 1
        return self.return_text


@pytest.mark.asyncio
async def test_llm_service_caching_24h():
    """
    Verifica que la segunda llamada con la misma cache_key no invoque al proveedor
    y retorne status='cached'.
    """
    provider = MockCustomProvider("Texto Generado Original")
    cache = AsyncTTLCache(default_ttl_seconds=86400)
    service = LLMService(provider=provider, cache=cache)

    key = service.build_cache_key("latencia", 30, "medium", "latam")
    assert key == "narrative:latencia:p26_50:medium:latam"

    # 1. Primera llamada -> invoca proveedor (status='success')
    res1 = await service.generate_narrative("Prompt test", cache_key=key)
    assert res1.status == "success"
    assert res1.cached is False
    assert res1.text == "Texto Generado Original"
    assert provider.call_count == 1

    # 2. Segunda llamada -> recupera de caché (status='cached')
    res2 = await service.generate_narrative("Prompt test", cache_key=key)
    assert res2.status == "cached"
    assert res2.cached is True
    assert res2.text == "Texto Generado Original"
    assert provider.call_count == 1  # No se incrementa


@pytest.mark.asyncio
async def test_llm_service_triggers_fallback_on_timeout():
    """
    Verifica que si el proveedor excede el timeout configurado, se active
    el fallback con status='timeout'.
    """
    class SlowProvider(BaseLLMProvider):
        name = "slow_provider"
        def validate_credentials(self) -> None: pass
        async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
            await asyncio.sleep(2.0)
            return "Demasiado tarde"

    service = LLMService(
        provider=SlowProvider(),
        timeout_seconds=0.1,  # Timeout agresivo de 100ms para el test
    )

    res = await service.generate_narrative(
        prompt="Genera algo",
        fallback_text="Recomendación fallback por timeout",
    )

    assert res.status == "timeout"
    assert res.text == "Recomendación fallback por timeout"
    assert res.cached is False


@pytest.mark.asyncio
async def test_llm_service_triggers_fallback_on_api_error():
    """
    Verifica que cualquier excepción del proveedor active el fallback con status='fallback'.
    """
    class FailingProvider(BaseLLMProvider):
        name = "failing_provider"
        def validate_credentials(self) -> None: pass
        async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
            raise httpx.ConnectError("Fallo de conexión a la API")

    service = LLMService(provider=FailingProvider())

    res = await service.generate_narrative(
        prompt="Genera algo",
        fallback_text="Recomendación fallback por error de API",
    )

    assert res.status == "fallback"
    assert res.text == "Recomendación fallback por error de API"
    assert res.cached is False


@pytest.mark.asyncio
async def test_llm_service_rate_limiter_exceeded_returns_rate_limited():
    """
    Verifica que al exceder la cuota del Rate Limiter, retorne status='rate_limited'
    y el fallback sin invocar al proveedor.
    """
    provider = MockCustomProvider("Texto")
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    service = LLMService(provider=provider, rate_limiter=limiter)

    # Request 1 -> permitido
    res1 = await service.generate_narrative("Prompt 1")
    assert res1.status == "success"
    assert provider.call_count == 1

    # Request 2 -> rate limited
    res2 = await service.generate_narrative(
        "Prompt 2", fallback_text="Fallback por rate limit"
    )
    assert res2.status == "rate_limited"
    assert res2.text == "Fallback por rate limit"
    assert provider.call_count == 1  # Proveedor no fue llamado
