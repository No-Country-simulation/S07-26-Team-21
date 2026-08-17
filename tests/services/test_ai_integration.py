import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.benchmark_output import NarrativesResponse
from app.services.llm_service import LLMResponse
from app.services.scoring_engine import generate_ai_insights


# ─────────────────────────────────────────────────────────────
# 1. Unit Tests: Concurrencia, Parseo y Fallbacks
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_ai_insights_executes_concurrently_and_parses_recommendations():
    """
    Verifica que generate_ai_insights llame concurrentemente al LLM,
    parsee las recomendaciones por salto de línea y marque llm_generated=True.
    """
    mock_responses = {
        "weakness": LLMResponse(
            text="Explicación contextual generada por IA para latencia.",
            status="success",
            provider="gemini",
        ),
        "practices": LLMResponse(
            text="Los operadores élite automatizan la gestión de cargas con IaC.",
            status="success",
            provider="gemini",
        ),
        "recs": LLMResponse(
            text="1. Implementar auto-scaling dinámico.\n2. Migrar scripts a Terraform.\n3. Configurar alertas proactivas.",
            status="success",
            provider="gemini",
        ),
    }

    async def mock_generate_narrative(prompt, cache_key=None, fallback_text=None):
        if "weakness" in (cache_key or ""):
            return mock_responses["weakness"]
        elif "practices" in (cache_key or ""):
            return mock_responses["practices"]
        else:
            return mock_responses["recs"]

    with patch("app.services.scoring_engine.llm_service.generate_narrative", side_effect=mock_generate_narrative) as mock_llm:
        narratives, recs, is_llm = await generate_ai_insights(
            dimension="latencia",
            user_score=2.5,
            percentile=20,
            facility_size="medium",
            region="latam",
            top_quartile_avg=4.8,
            gap=2.3,
        )

        assert mock_llm.call_count == 3
        assert is_llm is True
        assert narratives.llm_generated is True
        assert narratives.weakness_explanation == "Explicación contextual generada por IA para latencia."
        assert narratives.top_quartile_practices == "Los operadores élite automatizan la gestión de cargas con IaC."
        assert recs == [
            "Implementar auto-scaling dinámico.",
            "Migrar scripts a Terraform.",
            "Configurar alertas proactivas.",
        ]


@pytest.mark.asyncio
async def test_generate_ai_insights_graceful_fallback_on_partial_llm_failure():
    """
    Verifica que si una llamada del LLM falla o tira timeout, se active el fallback
    sin lanzar excepciones y llm_generated sea False.
    """
    async def mock_failing_narrative(prompt, cache_key=None, fallback_text=None):
        if "weakness" in (cache_key or ""):
            return LLMResponse(text=fallback_text, status="timeout")
        return LLMResponse(text="Respuesta OK", status="success")

    with patch("app.services.scoring_engine.llm_service.generate_narrative", side_effect=mock_failing_narrative):
        narratives, recs, is_llm = await generate_ai_insights(
            dimension="visibilidad",
            user_score=3.0,
            percentile=40,
            facility_size="small",
            region="europe",
            top_quartile_avg=4.5,
            gap=1.5,
        )

        # Como la debilidad falló (timeout), overall llm_generated debe ser False
        assert is_llm is False
        assert narratives.llm_generated is False
        # Debe contener el fallback estático curado
        assert "observabilidad cross-layer" in narratives.weakness_explanation


def test_narratives_response_schema_uses_utc_timezone():
    """
    Verifica que NarrativesResponse use timezone.utc para generated_at (sin datetime.utcnow deprecado).
    """
    narrative = NarrativesResponse(
        weakness_explanation="Texto explicativo",
        top_quartile_practices="Prácticas top",
    )
    assert narrative.generated_at is not None
    assert narrative.generated_at.tzinfo == timezone.utc


# ─────────────────────────────────────────────────────────────
# 2. Integration Test: POST /submit E2E con Narratives y Dynamic Recs
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_submit_endpoint_e2e_returns_201_with_narratives_and_dynamic_recommendations():
    """
    Verifica el ciclo completo del endpoint POST /api/v1/benchmark/submit,
    asegurando que retorne HTTP 201 y la estructura completa de narratives.
    """
    payload = {
        "facility_size": "medium",
        "region": "latam",
        "facility_type": "Enterprise Colocation",
        "p1": 3, "p2": 4, "p3": 3,
        "p4": 2, "p5": 2,
        "p6": 1, "p7": 2, "p8": 2,
        "p9": 3, "p10": 4,
        "p11": 3, "p12": 3, "p13": 2, "p14": 3, "p15": 3,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/benchmark/submit", json=payload)

    assert response.status_code == 201
    data = response.json()

    # 1. Validar Narratives
    assert "narratives" in data
    narratives = data["narratives"]
    assert "weakness_explanation" in narratives
    assert "top_quartile_practices" in narratives
    assert "llm_generated" in narratives
    assert "generated_at" in narratives
    assert len(narratives["weakness_explanation"]) > 10
    assert len(narratives["top_quartile_practices"]) > 10

    # 2. Validar Main Weakness Enriched
    assert "main_weakness" in data
    main_weakness = data["main_weakness"]
    assert "dimension" in main_weakness
    assert "user_score" in main_weakness
    assert "top_quartile_average" in main_weakness
    assert "gap" in main_weakness
    assert "recommendations" in main_weakness
    assert isinstance(main_weakness["recommendations"], list)
    assert len(main_weakness["recommendations"]) >= 1
