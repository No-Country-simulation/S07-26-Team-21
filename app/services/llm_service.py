from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Optional
import httpx
from pydantic import BaseModel, Field

from app.core.cache import AsyncTTLCache
from app.core.config import settings
from app.core.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Esquemas de Respuesta LLM
# ─────────────────────────────────────────────────────────────

class LLMResponse(BaseModel):
    """
    US-19: Estructura unificada de respuesta del servicio LLM.
    """

    text: str = Field(..., description="Texto o narrativa generada por el LLM o fallback")
    status: str = Field(
        ...,
        description="Estado del request: 'success', 'cached', 'fallback', 'timeout', 'rate_limited'",
    )
    provider: Optional[str] = Field(
        default=None, description="Nombre del proveedor que procesó el request"
    )
    cached: bool = Field(
        default=False, description="Indica si la respuesta fue recuperada de caché"
    )
    latency_ms: float = Field(
        default=0.0, description="Tiempo de respuesta en milisegundos"
    )


# ─────────────────────────────────────────────────────────────
# Interfaz Abstracta y Adaptadores de Proveedores
# ─────────────────────────────────────────────────────────────

class BaseLLMProvider(ABC):
    """
    Clase base abstracta para proveedores de LLM (Strategy Pattern).
    """

    name: str

    @abstractmethod
    def validate_credentials(self) -> None:
        """
        Valida tempranamente que las credenciales requeridas estén presentes (Fail-Fast).
        """
        pass

    @abstractmethod
    async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
        """
        Genera texto a partir de un prompt usando la API del proveedor.
        """
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Adaptador para Google Gemini (REST API).
    """

    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        validate: bool = True,
    ):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        if validate:
            self.validate_credentials()

    def validate_credentials(self) -> None:
        if not self.api_key or self.api_key.strip() == "":
            raise ValueError(
                "Configuración inválida: LLM_PROVIDER está configurado como 'gemini' "
                "pero GEMINI_API_KEY no está definida en el entorno (.env)."
            )

    async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            # 1. Intentar endpoint moderno /v1beta/interactions (Google Gemini 2026 Spec)
            try:
                url_interactions = "https://generativelanguage.googleapis.com/v1beta/interactions"
                payload_interactions = {"model": self.model, "input": prompt}
                resp = await client.post(
                    url_interactions, headers=headers, json=payload_interactions
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Caso A: output_text directo
                    if data.get("output_text"):
                        return str(data["output_text"]).strip()

                    # Caso B: Iterar steps buscando model_output (saltando pasos de pensamiento/thought)
                    for step in data.get("steps", []):
                        if step.get("type") in ("model_output", "modelOutput") or "content" in step:
                            content = step.get("content", [])
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        return str(item["text"]).strip()
                                    elif isinstance(item, str) and item.strip():
                                        return item.strip()
                        if "modelOutput" in step:
                            m_out = step["modelOutput"]
                            for item in m_out.get("content", []):
                                if isinstance(item, dict) and "text" in item:
                                    return str(item["text"]).strip()
            except Exception as e:
                logger.debug(f"[GeminiProvider] /interactions falló, probando generateContent: {e}")

            # 2. Endpoint estándar /v1beta/models/{self.model}:generateContent
            url_generate = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            )
            payload_generate = {"contents": [{"parts": [{"text": prompt}]}]}

            response = await client.post(
                url_generate, headers=headers, json=payload_generate
            )
            response.raise_for_status()
            data = response.json()

            # Extraer de candidates
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"].strip()

            if data.get("output_text"):
                return str(data["output_text"]).strip()

            raise ValueError(f"Respuesta de Gemini sin texto válido: {data}")




class ClaudeProvider(BaseLLMProvider):
    """
    Adaptador para Anthropic Claude (REST API).
    """

    name = "claude"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        validate: bool = True,
    ):
        self.api_key = api_key if api_key is not None else settings.CLAUDE_API_KEY
        self.model = model or settings.CLAUDE_MODEL
        if validate:
            self.validate_credentials()


    def validate_credentials(self) -> None:
        if not self.api_key or self.api_key.strip() == "":
            raise ValueError(
                "Configuración inválida: LLM_PROVIDER está configurado como 'claude' "
                "pero CLAUDE_API_KEY no está definida en el entorno (.env)."
            )

    async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content_list = data.get("content", [])
            if not content_list:
                raise ValueError("Respuesta de Claude vacía.")
            text = content_list[0]["text"]
            return text.strip()


class OllamaProvider(BaseLLMProvider):
    """
    Adaptador para Ollama local (REST API).
    """

    name = "ollama"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: str = "llama3",
        validate: bool = True,
    ):
        raw_url = base_url if base_url is not None else settings.OLLAMA_BASE_URL
        self.base_url = (raw_url or "").rstrip("/")
        self.model = model
        if validate:
            self.validate_credentials()

    def validate_credentials(self) -> None:
        if not self.base_url or self.base_url.strip() == "":
            raise ValueError(
                "Configuración inválida: LLM_PROVIDER está configurado como 'ollama' "
                "pero OLLAMA_BASE_URL no está definida en el entorno (.env)."
            )


    async def generate(self, prompt: str, timeout_seconds: float = 5.0) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "")
            return text.strip()


# ─────────────────────────────────────────────────────────────
# Orquestador Centralizado: LLMService
# ─────────────────────────────────────────────────────────────

def get_provider_factory(
    provider_name: str,
    validate_on_init: bool = False,
) -> BaseLLMProvider:
    """
    Factoría de proveedores según el nombre ('gemini', 'claude', 'ollama').
    """
    p_name = provider_name.lower()
    if p_name == "gemini":
        return GeminiProvider(validate=validate_on_init)
    elif p_name == "claude":
        return ClaudeProvider(validate=validate_on_init)
    elif p_name == "ollama":
        return OllamaProvider(validate=validate_on_init)
    else:
        raise ValueError(
            f"Proveedor LLM desconocido '{provider_name}'. Opciones: 'gemini', 'claude', 'ollama'"
        )


class LLMService:
    """
    Servicio centralizado y agnóstico de proveedores LLM.
    Orquesta llamadas a la API remota con caching TTL de 24h, Rate Limiting (30 req/min),
    timeouts estrictos de 5s y degradación suave mediante fallback.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        cache: Optional[AsyncTTLCache] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
        timeout_seconds: Optional[float] = None,
        validate_on_init: bool = False,
    ):
        self.provider = provider or get_provider_factory(
            settings.LLM_PROVIDER, validate_on_init=validate_on_init
        )
        self.cache = cache or AsyncTTLCache(default_ttl_seconds=86400)
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            max_requests=settings.LLM_RATE_LIMIT_PER_MINUTE, window_seconds=60.0
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.LLM_TIMEOUT_SECONDS
        )

    @staticmethod
    def build_cache_key(
        dimension: str,
        percentile: int,
        facility_size: str,
        region: str,
    ) -> str:
        """
        Construye la clave canónica de caché:
        narrative:{dimension}:{percentile_range}:{size}:{region}
        """
        if percentile <= 25:
            pct_range = "p0_25"
        elif percentile <= 50:
            pct_range = "p26_50"
        elif percentile <= 75:
            pct_range = "p51_75"
        else:
            pct_range = "p76_100"

        return (
            f"narrative:{dimension.lower()}:{pct_range}:"
            f"{facility_size.lower()}:{region.lower()}"
        )

    def get_default_fallback(self) -> str:
        return (
            "1. Implementar telemetría y monitoreo centralizado en tiempo real.\n"
            "2. Optimizar redundancia y eficiencia energética en sistemas críticos.\n"
            "3. Reducir la latencia operativa mediante automatización de flujos de trabajo."
        )

    async def generate_narrative(
        self,
        prompt: str,
        cache_key: Optional[str] = None,
        fallback_text: Optional[str] = None,
    ) -> LLMResponse:
        """
        Genera una narrativa de benchmark.
        Aplica:
        1. Cache Check (24 horas)
        2. Rate Limiting (30 req/min)
        3. Timeout de 5s y degradación a fallback en errores
        """
        start_time = time.monotonic()
        fallback_val = fallback_text or self.get_default_fallback()

        # 1. Verificar Caché (si se suministró cache_key)
        if cache_key:
            cached_val = await self.cache.get(cache_key)
            if cached_val is not None:
                logger.info(
                    f"[LLMService] Cache Hit para key='{cache_key}' (provider={self.provider.name})"
                )
                return LLMResponse(
                    text=cached_val,
                    status="cached",
                    provider=self.provider.name,
                    cached=True,
                    latency_ms=0.0,
                )

        # 2. Rate Limiting Check
        allowed = await self.rate_limiter.acquire()
        if not allowed:
            logger.warning(
                f"[LLMService] Rate limit excedido ({settings.LLM_RATE_LIMIT_PER_MINUTE} req/min). "
                f"Retornando fallback."
            )
            return LLMResponse(
                text=fallback_val,
                status="rate_limited",
                provider=self.provider.name,
                cached=False,
                latency_ms=0.0,
            )

        # 3. Invocar al proveedor con Timeout estricto de 5 segundos
        try:
            generated_text = await asyncio.wait_for(
                self.provider.generate(prompt, timeout_seconds=self.timeout_seconds),
                timeout=self.timeout_seconds,
            )

            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                f"[LLMService] Generación exitosa ({self.provider.name}) en {latency_ms}ms"
            )

            # Guardar en caché si hay cache_key
            if cache_key and generated_text:
                await self.cache.set(cache_key, generated_text)

            return LLMResponse(
                text=generated_text,
                status="success",
                provider=self.provider.name,
                cached=False,
                latency_ms=latency_ms,
            )

        except asyncio.TimeoutError:
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(
                f"[LLMService] Timeout (> {self.timeout_seconds}s) invocando a {self.provider.name}. "
                f"Activando fallback."
            )
            return LLMResponse(
                text=fallback_val,
                status="timeout",
                provider=self.provider.name,
                cached=False,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(
                f"[LLMService] Error invocando a {self.provider.name}: {exc}. "
                f"Activando fallback."
            )
            return LLMResponse(
                text=fallback_val,
                status="fallback",
                provider=self.provider.name,
                cached=False,
                latency_ms=latency_ms,
            )


# Instancia singleton por defecto
llm_service = LLMService(validate_on_init=False)
