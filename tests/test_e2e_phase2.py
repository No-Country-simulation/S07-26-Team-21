"""
tests/test_e2e_phase2.py

US-21: Testing de Integración Fase 2 (E2E)
===========================================

Tests que verifican el flujo completo de Fase 2:
  1. Narrativas generadas por IA (o fallback)
  2. Caching de LLM (hit <50ms, miss >100ms)
  3. Fallback cuando LLM falla (timeout, error)
  4. Peer comparison funciona correctamente
  5. Múltiples usuarios generan 1 LLM call si son "iguales"
  6. Rate limiting no bloquea flujo normal
  7. GET /stats retorna agregaciones

Correr con: pytest tests/test_e2e_phase2.py -v -s
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import AsyncTTLCache
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_output import BenchmarkResponse
from app.services.llm_service import LLMResponse, LLMService


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 1: POST /submit retorna BenchmarkResponse completo
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_submit_returns_complete_response(
    async_client: httpx.AsyncClient, db: AsyncSession
):
    """
    POST /submit con payload válido
       retorna BenchmarkResponse con narrativas, scores, percentiles.
    """
    payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 3,
        "p2": 4,
        "p3": 2,
        "p4": 2,
        "p5": 3,
        "p6": 4,
        "p7": 3,
        "p8": 2,
        "p9": 3,
        "p10": 3,
        "p11": 2,
        "p12": 2,
        "p13": 1,
        "p14": 2,
        "p15": 1,
    }

    response = await async_client.post("/api/v1/benchmark/submit", json=payload)

    assert response.status_code == 201
    data = response.json()

    # Verificar estructura del BenchmarkResponse
    assert "evaluation_id" in data
    assert "user_context" in data
    assert data["user_context"]["facility_size"] == "medium"
    assert data["user_context"]["region"] == "latam"

    # Verificar scores
    assert "scores_likert" in data
    assert "visibilidad" in data["scores_likert"]
    assert "friccion" in data["scores_likert"]
    assert "latencia" in data["scores_likert"]
    assert "auto_cuantificacion" in data["scores_likert"]
    assert "bloqueantes" in data["scores_likert"]

    # Verificar percentiles
    assert "percentiles" in data
    assert "general" in data["percentiles"]

    # Verificar main_weakness enriquecido
    assert "main_weakness" in data
    assert "dimension" in data["main_weakness"]
    assert "gap" in data["main_weakness"]
    assert "recommendations" in data["main_weakness"]

    # Verificar narrativas presentes
    assert "narratives" in data
    assert "weakness_explanation" in data["narratives"]
    assert "top_quartile_practices" in data["narratives"]


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 2: Caching funciona (hit <50ms, miss >100ms)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_caching_performance():
    """
    LLMService cachea narrativas
       - Primer call: ~100ms (sin cache)
       - Segundo call: <50ms (con cache)
    """
    cache = AsyncTTLCache(default_ttl_seconds=3600)
    rate_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60.0)

    mock_provider = AsyncMock()
    mock_provider.name = "mock"

    async def slow_generate(prompt, timeout_seconds=5.0):
        await asyncio.sleep(0.1)  # 100ms
        return "Narrativa después de 100ms de latencia"

    mock_provider.generate = slow_generate

    llm_service = LLMService(
        provider=mock_provider, cache=cache, rate_limiter=rate_limiter
    )

    # Primer call: miss
    start = time.monotonic()
    resp1 = await llm_service.generate_narrative(
        prompt="Test prompt", cache_key="test_narrative:bloqueantes:p26_50:medium:latam"
    )
    latency1 = (time.monotonic() - start) * 1000

    assert resp1.status == "success"
    assert latency1 > 90  # Debería tardar ~100ms
    assert latency1 < 5000  # El miss debe respetar el límite de 5 segundos

    # Segundo call: hit
    start = time.monotonic()
    resp2 = await llm_service.generate_narrative(
        prompt="Test prompt", cache_key="test_narrative:bloqueantes:p26_50:medium:latam"
    )
    latency2 = (time.monotonic() - start) * 1000

    assert resp2.status == "cached"
    assert latency2 < 50  # Debería ser casi instantáneo

    # Verificar que es el mismo contenido
    assert resp1.text == resp2.text


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 3: Fallback si LLM falla (timeout)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_fallback_on_timeout():
    """
     Si LLM hace timeout (>5s)
       retorna fallback + status="timeout".
    """
    cache = AsyncTTLCache(default_ttl_seconds=3600)
    rate_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60.0)

    mock_provider = AsyncMock()
    mock_provider.name = "mock"

    async def timeout_generate(prompt, timeout_seconds=5.0):
        await asyncio.sleep(6.0)  # Más de 5s → timeout
        raise asyncio.TimeoutError()

    mock_provider.generate = timeout_generate

    llm_service = LLMService(
        provider=mock_provider,
        cache=cache,
        rate_limiter=rate_limiter,
        timeout_seconds=0.1,  # 100ms timeout muy corto para forzar timeout
    )

    # Llamar con timeout corto
    resp = await llm_service.generate_narrative(
        prompt="Test prompt", cache_key="test_timeout"
    )

    # Debe retornar fallback
    assert resp.status == "timeout"
    assert resp.text is not None  # Fallback text
    assert len(resp.text) > 0  # No está vacío
    assert "ERROR" not in resp.text.upper()


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 4: Múltiples usuarios con mismo perfil → cache hits
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_users_same_profile_cache_hit(async_client: httpx.AsyncClient):
    """
    Dos usuarios con mismo tamaño/región/debilidad
       → cache_key igual → LLMService.generate_narrative() llamado 3 veces (weakness, practices, recs)
       → Segundo usuario: 0 llamadas adicionales (todo es cache hit)
    """
    cache = AsyncTTLCache(default_ttl_seconds=3600)
    rate_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60.0)

    # Mock provider que CUENTA cuántas veces es llamado
    call_count = 0

    async def counting_generate(prompt, timeout_seconds=5.0):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "IA response"

    mock_provider = AsyncMock()
    mock_provider.name = "mock"
    mock_provider.generate = counting_generate

    llm_service = LLMService(
        provider=mock_provider, cache=cache, rate_limiter=rate_limiter
    )

    payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 3,
        "p2": 4,
        "p3": 2,
        "p4": 2,
        "p5": 3,
        "p6": 4,
        "p7": 3,
        "p8": 2,
        "p9": 3,
        "p10": 3,
        "p11": 2,
        "p12": 2,
        "p13": 1,
        "p14": 2,
        "p15": 1,
    }

    with patch("app.services.scoring_engine.llm_service", new=llm_service):
        first_response = await async_client.post(
            "/api/v1/benchmark/submit", json=payload
        )
        second_response = await async_client.post(
            "/api/v1/benchmark/submit", json=payload
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert call_count == 3  # 3 narrativas para el primer usuario, 0 para el segundo


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 5: Peer Comparison funciona con múltiples usuarios
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_peer_comparison_multiple_users(async_client: httpx.AsyncClient):
    """
    Con 5+ usuarios del mismo tamaño/región
       → POST /submit retorna peer_comparison calculado.
    """
    # Insertar 5 usuarios primero
    for i in range(5):
        payload = {
            "facility_size": "medium",
            "region": "latam",
            "p1": 1 + i,
            "p2": 4,
            "p3": 2,
            "p4": 2,
            "p5": 3,
            "p6": 4,
            "p7": 3,
            "p8": 2,
            "p9": 3,
            "p10": 3,
            "p11": 2,
            "p12": 2,
            "p13": 1,
            "p14": 2,
            "p15": 1,
        }
        await async_client.post("/api/v1/benchmark/submit", json=payload)

    # Ahora hacer un submit que debería comparar contra los 5 peers
    payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 3,
        "p2": 4,
        "p3": 2,
        "p4": 2,
        "p5": 3,
        "p6": 4,
        "p7": 3,
        "p8": 2,
        "p9": 3,
        "p10": 3,
        "p11": 2,
        "p12": 2,
        "p13": 1,
        "p14": 2,
        "p15": 1,
    }
    response = await async_client.post("/api/v1/benchmark/submit", json=payload)

    assert response.status_code == 201
    data = response.json()

    # Verificar que peer_comparison existe
    assert "peer_comparison" in data
    peer_comp = data["peer_comparison"]

    # Con 5+ peers, debe tener datos
    if peer_comp.get("peers_count", 0) >= 3:
        assert peer_comp.get("peer_average_score") is not None
        assert peer_comp.get("gap_vs_peers") is not None
        assert peer_comp.get("percentile_vs_peers") is not None


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 6: Rate Limiting no bloquea dentro de limites
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limiting_within_limits():
    """
    10 requests dentro del límite (30/min)
       → todos retornan status != "rate_limited".
    """
    cache = AsyncTTLCache(default_ttl_seconds=3600)
    rate_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60.0)

    mock_provider = AsyncMock()
    mock_provider.name = "mock"
    mock_provider.generate = AsyncMock(return_value="Mock IA response")

    llm_service = LLMService(
        provider=mock_provider, cache=cache, rate_limiter=rate_limiter
    )

    # Hacer 10 requests
    for i in range(10):
        resp = await llm_service.generate_narrative(
            prompt=f"Prompt {i}", cache_key=f"key_{i}"
        )
        assert resp.status != "rate_limited"


# ─────────────────────────────────────────────────────────────
# US-21 Escenario 7: GET /stats retorna agregaciones (NUEVO)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_stats_e2e(async_client: httpx.AsyncClient):
    """
    GET /api/v1/benchmark/stats retorna agregaciones
       - total_evaluations >= 1
       - average_scores por dimensión
       - general_average
    """
    # 1. POST una evaluación primero
    payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 4,
        "p2": 4,
        "p3": 4,
        "p4": 3,
        "p5": 3,
        "p6": 2,
        "p7": 2,
        "p8": 2,
        "p9": 4,
        "p10": 4,
        "p11": 3,
        "p12": 3,
        "p13": 3,
        "p14": 3,
        "p15": 3,
    }
    submit_res = await async_client.post("/api/v1/benchmark/submit", json=payload)
    assert submit_res.status_code == 201

    # 2. Retrieve agregaciones
    stats_res = await async_client.get("/api/v1/benchmark/stats")
    assert stats_res.status_code == 200

    data = stats_res.json()
    assert "total_evaluations" in data
    assert data["total_evaluations"] >= 1
    assert "average_scores" in data
    assert "general_average" in data

