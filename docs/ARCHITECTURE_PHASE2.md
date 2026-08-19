# 🏛️ Arquitectura del Sistema - Fase 2: Narrativas IA y Estadísticas Agregadas

Este documento detalla la arquitectura de extremo a extremo implementada en la **Fase 2** del motor **BENCHMARK·DC**, incluyendo el procesamiento concurrente de IA, la persistencia en PostgreSQL, la estrategia de caché reactiva y las garantías de privacidad.

---

## 1. 🔄 Ciclo de Vida Completo de una Evaluación (`POST /submit`)

```mermaid
sequenceDiagram
    autonumber
    actor User as Frontend / Operador
    participant API as FastAPI (/api/v1/benchmark)
    participant Engine as Scoring Engine
    participant DB as PostgreSQL (AsyncSession)
    participant Cache as AsyncTTLCache (24h)
    participant LLM as LLMService (Gemini/Claude/Ollama)
    participant Fallback as Static Maps (Curados)

    User->>API: POST /benchmark/submit (15 respuestas + contexto)
    API->>Engine: process_evaluation(payload, db)
    
    rect rgb(240, 248, 255)
        note over Engine: 1. Scoring & Normalización
        Engine->>Engine: Calcular scores Likert (1.0 - 5.0)
        Engine->>Engine: Calcular percentiles combinados (Público + Privado)
        Engine->>Engine: Identificar Main Weakness (gap contra Top 25%)
    end

    Engine->>DB: Persistir UserEvaluation (anónima, UUID)
    DB-->>Engine: Confirmación de guardado

    rect rgb(255, 250, 240)
        note over Engine, LLM: 2. Inferencia Concurrente (asyncio.gather)
        par Rama 1: Weakness Explanation
            Engine->>Cache: Get narrative:weakness:...
            alt Cache Hit
                Cache-->>Engine: Texto en caché (<50ms)
            else Cache Miss
                Engine->>LLM: Invocación LLM (Timeout 25s)
                alt LLM Exitoso
                    LLM-->>Engine: Explicación IA generada
                    Engine->>Cache: Guardar en caché (TTL 24h)
                else Error / Timeout
                    Engine->>Fallback: STATIC_EXPLANATION_MAP[dim]
                    Fallback-->>Engine: Explicación técnica estática
                end
            end
        and Rama 2: Top Quartile Practices
            Engine->>Cache: Get narrative:practices:...
            alt Cache Hit
                Cache-->>Engine: Texto en caché (<50ms)
            else Cache Miss
                Engine->>LLM: Invocación LLM (Timeout 25s)
                alt LLM Exitoso
                    LLM-->>Engine: Prácticas élite IA
                    Engine->>Cache: Guardar en caché (TTL 24h)
                else Error / Timeout
                    Engine->>Fallback: STATIC_PRACTICES_MAP[dim]
                    Fallback-->>Engine: Prácticas élite estáticas
                end
            end
        and Rama 3: Dynamic Recommendations
            Engine->>Cache: Get narrative:recs:...
            alt Cache Hit
                Cache-->>Engine: Texto en caché (<50ms)
            else Cache Miss
                Engine->>LLM: Invocación LLM (Timeout 25s)
                alt LLM Exitoso
                    LLM-->>Engine: 3 Recomendaciones IA
                    Engine->>Cache: Guardar en caché (TTL 24h)
                else Error / Timeout
                    Engine->>Fallback: RECOMMENDATIONS_MAP[dim]
                    Fallback-->>Engine: 3 Recomendaciones estáticas
                end
            end
        end
    end

    rect rgb(245, 255, 245)
        note over Engine, DB: 3. Peer Comparison & Rebalanceo
        Engine->>DB: Query peers (mismo tamaño y región)
        DB-->>Engine: Dataset de pares (K-anonimato >= 3)
        Engine->>Engine: Calcular peer_average, gap y percentil relativo
        Engine->>Engine: Calcular pesos de rebalanceo dinámico
    end

    Engine-->>API: BenchmarkResponse (completa)
    API->>Cache: Invalidar caché de estadísticas (/stats)
    API-->>User: HTTP 201 Created (JSON estructurado)
```

---

## 2. 📊 Estadísticas de Plataforma e Invalidación Reactiva (`GET /stats`)

Para evitar consultas de agregación costosas en bases de datos con miles de registros, `StatsService` implementa una caché con **TTL de 1 hora** e **invalidación reactiva inmediata**:

```mermaid
graph TD
    A[Cliente: GET /api/v1/benchmark/stats] --> B{¿Existe en caché?}
    B -- Sí (Cache Hit) --> C[Retornar BenchmarkStatsResponse en <5ms]
    B -- No (Cache Miss / Expirado) --> D[Query Agregada PostgreSQL: AVG por dimensión, COUNT total]
    D --> E[Almacenar en caché con TTL de 3600s]
    E --> F[Retornar BenchmarkStatsResponse]

    G[Nuevo POST /api/v1/benchmark/submit exitoso] --> H[StatsService.invalidate_cache]
    H --> I[Caché invalidada inmediatamente]
```

---

## 3. 🛡️ Arquitectura de Privacidad por Diseño (Privacy by Design)

```mermaid
flowchart LR
    subgraph Ingestion["1. Ingestión"]
        A[Datos del Formulario] --> B[Generar UUID v4]
        A --> C[Descartar IPs, dominios y nombres corporativos]
    end

    subgraph Storage["2. Almacenamiento Anónimo"]
        B & C --> D[(PostgreSQL: UserEvaluation)]
        D --> E[Generalización: Rango de tamaño y Región]
    end

    subgraph Comparison["3. Comparación de Pares"]
        E --> F{Peers count >= 3?}
        F -- Sí --> G[Calcular Gap vs Peers]
        F -- No --> H[Disclaimer K-Anonimato: 'No hay suficientes datos']
    end
```

---

## 4. 🧩 Estructura Modular de Componentes

| Módulo | Responsabilidad Principal |
| :--- | :--- |
| `app/services/scoring_engine.py` | Cálculo de scores, percentiles, debilidad crítica, orquestación de `generate_ai_insights` (3 llamadas concurrentes) y peer comparison. |
| `app/services/llm_service.py` | Servicio centralizado agnóstico a proveedores con `AsyncTTLCache`, `SlidingWindowRateLimiter` y adaptadores (Gemini, Claude, Ollama). |
| `app/services/stats_service.py` | Agregaciones estadísticas de plataforma con caché en memoria de 1 hora e invalidación reactiva. |
| `app/core/rate_limiter.py` | Control de tasa basado en ventana deslizante con poda automática de timestamps para evitar fugas de memoria. |
| `app/core/cache.py` | Implementación asíncrona de caché en memoria con expiración por tiempo (TTL). |
| `app/schemas/benchmark_output.py` | Contratos Pydantic de salida (`BenchmarkResponse`, `NarrativesResponse`, `MainWeaknessEnriched`). |
| `app/schemas/benchmark_stats.py` | Contratos Pydantic de estadísticas agregadas (`BenchmarkStatsResponse`). |
