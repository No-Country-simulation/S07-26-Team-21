# 🚀 BENCHMARK·DC Engine

<p align="center">
  <b>Language Navigation / Navegación por Idioma / Navegação por Idioma</b><br>
  <a href="#-español">🇪🇸 Español</a> •
  <a href="#-english">🇬🇧 English</a> •
  <a href="#-português">🇧🇷 Português</a>
</p>

---

# 🇪🇸 Español

### Motor de Benchmark de Madurez Operativa para Data Centers con Inteligencia Artificial

Plataforma integral diseñada para evaluar el nivel de madurez operativa de centros de datos mediante un sistema de benchmarking cuantitativo (Likert 1-5, percentiles, rebalanceo dinámico público/privado) y cualitativo impulsado por **Inteligencia Artificial generativa concurrente (Fase 2)**.

El sistema entrega un diagnóstico instantáneo, anónimo y accionable que posiciona al operador respecto a la industria, compara sus resultados contra *peers* del mismo segmento (K-anonimato) y genera explicaciones contextuales y recomendaciones técnicas de élite.

---

## 🌟 Características Principales

### Fase 1: Motor Estadístico y Privacidad
* **Evaluación Multidimensional:** 15 indicadores estructurados en 5 dimensiones clave (*Visibilidad*, *Fricción*, *Latencia*, *Auto-cuantificación*, *Bloqueantes*).
* **Percentiles Reales:** Algoritmo de rango percentil sobre datasets públicos de la industria y evaluaciones privadas anonimizadas.
* **Motor de Rebalanceo Dinámico:** Ponderación progresiva que reduce el peso del dataset público a medida que crece la base privada.
* **Comparación Relativa contra Peers:** Comparativa segmentada por región y escala con salvaguarda estricta de privacidad (**K-anonimato** $k \ge 3$).

### Fase 2: Narrativas de IA y Resiliencia de Producción
* **Servicio LLM Centralizado y Agnóstico:** Arquitectura desacoplada compatible con **Google Gemini** (Interactions API / Spec 2026), **Anthropic Claude** y **Ollama**.
* **Generación Concurrente (`asyncio.gather`):** Disparo simultáneo de 3 inferencias (Explicación de debilidad, Prácticas del cuartil superior y Recomendaciones técnicas dinámicas) para mínima latencia.
* **Estrategia de Caching con TTL de 24h:** Claves canónicas `narrative:{dim}:{pct}:{size}:{region}` con tiempos de respuesta `<50ms` en *Cache Hits*.
* **Degradación Suave (Graceful Fallback):** Transición automática y transparente a fallbacks técnicos curados ante caídas o límites de cuota de API.
* **Control de Tasa (Rate Limiting):** Ventana deslizante de 30 req/min con poda de memoria reactiva.
* **Estadísticas Globales de Plataforma:** Endpoint `GET /api/v1/benchmark/stats` con caché de 1 hora e invalidación reactiva.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Backend Framework** | Python 3.12+ • FastAPI • Pydantic v2 • Pydantic Settings |
| **Base de Datos** | PostgreSQL 16 • SQLAlchemy 2.0 (AsyncIO) • asyncpg • Alembic |
| **LLM & IA** | Google Gemini API (Interactions API / Spec 2026) • Anthropic Claude • Ollama • HTTPX |
| **Caché y Resiliencia** | In-Memory AsyncTTLCache • SlidingWindowRateLimiter • AsyncIO |
| **Testing** | Pytest • Pytest-AsyncIO • Coverage (242+ tests unitarios y E2E) |

---

## 📚 Documentación del Proyecto

El repositorio cuenta con guías técnicas exhaustivas en el directorio `docs/`:

* 🧠 [**docs/LLM_SETUP.md**](docs/LLM_SETUP.md): Configuración de proveedores LLM (Gemini, Claude, Ollama), caché y resolución de problemas.
* 🏛️ [**docs/ARCHITECTURE_PHASE2.md**](docs/ARCHITECTURE_PHASE2.md): Diagramas de secuencia y flujo de datos de la Fase 2.
* 💻 [**docs/SETUP-BACK.md**](docs/SETUP-BACK.md): Guía paso a paso para levantar Docker, ejecutar migraciones de Alembic y seed inicial.

---

## 🌐 Endpoints de la API

La API expone sus contratos bajo el prefijo `/api/v1` con documentación interactiva en **`/docs`** (Swagger UI) y **`/redoc`**:

| Método | Endpoint | Descripción |
| :---: | :--- | :--- |
| `POST` | `/api/v1/benchmark/submit` | Procesa las 15 respuestas, calcula scores/percentiles y retorna el diagnóstico completo con IA. |
| `GET` | `/api/v1/benchmark/stats` | Retorna métricas globales agregadas de la plataforma (con caché de 1h e invalidación reactiva). |
| `GET` | `/` | Endpoint raíz de bienvenida y health check. |

---

## 🚀 Guía de Inicio Rápido

### 1. Clonar el repositorio y configurar el entorno
```bash
git clone https://github.com/No-Country-simulation/S07-26-Team-21.git
cd S07-26-Team-21/backend
python -m venv venv
```

* **Activar entorno virtual:**
  * Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
  * Linux/macOS: `source venv/bin/activate`

```bash
pip install -r requirements.txt
cp .env.example .env
```

### 2. Levantar la Base de Datos con Docker
```bash
docker compose up -d
```

### 3. Ejecutar Migraciones y Carga Inicial (Seed)
```bash
alembic upgrade head
python seed.py
```

### 4. Iniciar el Servidor de Desarrollo
```bash
uvicorn app.main:app --reload
```
Acceder a la documentación interactiva en: [http://localhost:8000/docs](http://localhost:8000/docs).

### 5. Ejecutar la Suite de Pruebas Automatizadas
```bash
pytest -v
```

---

## 🔒 Privacidad y Seguridad por Diseño

* **Pseudonimización:** Identificadores UUID v4 sin almacenamiento de razones sociales, dominios ni direcciones IP.
* **K-Anonimato:** Las métricas de comparación de pares solo se calculan cuando existen al menos 3 evaluaciones independientes en el mismo segmento.
* **CORS Seguro:** Configuración restrictiva de orígenes autorizados (`BACKEND_CORS_ORIGINS`) para desarrollo y producción.
* **Seguridad de Secretos:** Claves de API enviadas mediante headers HTTP dedicados (`x-goog-api-key`, `x-api-key`), excluidas de URLs y logs.

---

## 👥 Equipo de Desarrollo

| Integrante       | Rol                               | País                   |
| ---------------- | --------------------------------- | ---------------------- |
| Tomas Quiroz     | Data Science                      | 🇨🇴 Colombia (UTC-5)  |
| Luis Calegari    | Backend Lead                      | 🇦🇷 Argentina (UTC-3) |
| Geraldin Nuñez   | Frontend                          | 🇵🇪 Perú (UTC-5)      |
| Pedro Vallejos   | Backend                           | 🇦🇷 Argentina (UTC-3) |
| Jovany Alvarez   | Backend                           | 🇲🇽 México (UTC-6)    |
| José Lugo        | Backend                           | 🇨🇱 Chile (UTC-4)     |
| Brenis Hernandez | Data Analyst                      | 🇲🇽 México (UTC-6)    |
| Juan Alvarez     | Data Analyst/Backend/Scrum Master | 🇦🇷 Argentina (UTC-3) |

---
---

# 🇬🇧 English

### Data Center Operational Maturity Benchmark Engine with Artificial Intelligence

A comprehensive platform designed to assess the operational maturity level of modern data centers through quantitative benchmarking (Likert 1-5, percentiles, dynamic public/private rebalancing) and qualitative insights powered by **concurrent Generative AI (Phase 2)**.

The system delivers an instant, anonymous, and actionable diagnosis that positions the operator within the industry, compares results against segment *peers* (K-anonymity), and generates contextual explanations and elite technical recommendations.

---

## 🌟 Key Features

### Phase 1: Statistical Engine & Privacy
* **Multidimensional Evaluation:** 15 metrics across 5 key dimensions (*Visibility*, *Friction*, *Latency*, *Self-Quantification*, *Blockers*).
* **True Percentiles:** Count-based percentile rank algorithm over industry public datasets and private anonymized submissions.
* **Dynamic Rebalancing Engine:** Progressive Bayesian weighting that shifts reliance from public benchmarks to verified private industry data.
* **Relative Peer Comparison:** Regional and scale-segmented comparative analytics backed by **K-anonymity** ($k \ge 3$).

### Phase 2: AI Narratives & Production Resilience
* **Centralized Agnostic LLM Service:** Decoupled architecture supporting **Google Gemini** (Interactions API / 2026 Spec), **Anthropic Claude**, and **Ollama**.
* **Concurrent Generation (`asyncio.gather`):** Simultaneous dispatch of 3 AI inferences (Weakness Explanation, Top Quartile Practices, and Dynamic Recommendations) for sub-second latency overhead.
* **24-Hour TTL Caching:** Collision-free canonical keys `narrative:{dim}:{pct}:{size}:{region}` delivering `<50ms` response times on *Cache Hits*.
* **Graceful Fallbacks:** Seamless, automated fallback to curated technical catalogs during API outages or rate limits.
* **Rate Limiting:** Sliding-window limiter (30 req/min) with proactive memory leak mitigation.
* **Global Platform Statistics:** `GET /api/v1/benchmark/stats` endpoint with 1-hour in-memory cache and reactive invalidation on new submissions.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Python 3.12+ • FastAPI • Pydantic v2 • Pydantic Settings |
| **Database** | PostgreSQL 16 • SQLAlchemy 2.0 (AsyncIO) • asyncpg • Alembic |
| **LLM & AI** | Google Gemini API (Interactions API / 2026 Spec) • Anthropic Claude • Ollama • HTTPX |
| **Caching & Resilience** | In-Memory AsyncTTLCache • SlidingWindowRateLimiter • AsyncIO |
| **Testing** | Pytest • Pytest-AsyncIO • Coverage (242+ unit and E2E tests) |

---

## 📚 Project Documentation

Detailed guides are available in the `docs/` directory:

* 🧠 [**docs/LLM_SETUP.md**](docs/LLM_SETUP.md): Provider setup (Gemini, Claude, Ollama), caching policies, and troubleshooting.
* 🏛️ [**docs/ARCHITECTURE_PHASE2.md**](docs/ARCHITECTURE_PHASE2.md): Sequence and data flow diagrams for Phase 2.
* 💻 [**docs/SETUP-BACK.md**](docs/SETUP-BACK.md): Step-by-step instructions for Docker, Alembic migrations, and database seeding.

---

## 🌐 API Endpoints

All endpoints are served under `/api/v1` with interactive documentation at **`/docs`** (Swagger UI) and **`/redoc`**:

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `POST` | `/api/v1/benchmark/submit` | Evaluates 15 answers, computes scores/percentiles, and returns the full AI diagnosis. |
| `GET` | `/api/v1/benchmark/stats` | Retrieves aggregated platform statistics (1-hour cache with reactive invalidation). |
| `GET` | `/` | Root health check and welcome endpoint. |

---

## 🚀 Quickstart Guide

### 1. Clone the repository and configure environment
```bash
git clone https://github.com/No-Country-simulation/S07-26-Team-21.git
cd S07-26-Team-21/backend
python -m venv venv
```

* **Activate virtual environment:**
  * Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
  * Linux/macOS: `source venv/bin/activate`

```bash
pip install -r requirements.txt
cp .env.example .env
```

### 2. Start PostgreSQL with Docker
```bash
docker compose up -d
```

### 3. Run Migrations and Seed Industry Benchmarks
```bash
alembic upgrade head
python seed.py
```

### 4. Start Development Server
```bash
uvicorn app.main:app --reload
```
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs).

### 5. Run Automated Test Suite
```bash
pytest -v
```

---

## 🔒 Privacy & Security by Design

* **Pseudonymization:** Pure UUID v4 identifiers; no company names, domain names, or IP addresses are persisted.
* **K-Anonymity:** Peer comparison metrics require a minimum cohort of $k \ge 3$ independent peers.
* **Secure CORS:** Strict origin whitelisting (`BACKEND_CORS_ORIGINS`) across environments.
* **Secret Isolation:** Dedicated HTTP headers (`x-goog-api-key`, `x-api-key`) exclude API keys from URL parameters and access logs.

---
---

# 🇧🇷 Português

### Motor de Benchmark de Maturidade Operacional para Data Centers com Inteligência Artificial

Plataforma integrada desenvolvida para avaliar o nível de maturidade operacional de centros de dados por meio de um sistema de benchmarking quantitativo (Likert 1-5, percentis, rebalanceamento dinâmico público/privado) e qualitativo impulsionado por **Inteligência Artificial generativa concorrente (Fase 2)**.

O sistema fornece um diagnóstico instantâneo, anônimo e acionável que posiciona o operador em relação à indústria, compara seus resultados com *peers* do mesmo segmento (K-anonimato) e gera explicações contextuais e recomendações técnicas de elite.

---

## 🌟 Principais Recursos

### Fase 1: Motor Estatístico e Privacidade
* **Avaliação Multidimensional:** 15 indicadores estruturados em 5 dimensões essenciais (*Visibilidade*, *Fricção*, *Latência*, *Auto-quantificação*, *Bloqueadores*).
* **Percentis Reais:** Algoritmo de classificação percentual baseado em contagem sobre datasets públicos da indústria e avaliações privadas anonimizadas.
* **Motor de Rebalanceamento Dinâmico:** Ponderação progressiva bayesiana que reduz o peso do dataset público à medida que a base privada se expande.
* **Comparação Relativa com Pares (Peers):** Análise comparativa regional e por porte protegida por **K-anonimato** ($k \ge 3$).

### Fase 2: Narrativas com IA e Resiliência em Produção
* **Serviço LLM Centralizado e Agnóstico:** Arquitetura desacoplada compatível com **Google Gemini** (Interactions API / Spec 2026), **Anthropic Claude** e **Ollama**.
* **Geração Concorrente (`asyncio.gather`):** Execução paralela de 3 inferências de IA (Explicação do Ponto Fraco, Práticas do Quartil Superior e Recomendações Técnicas Dinâmicas) com latência reduzida.
* **Estratégia de Cache com TTL de 24h:** Chaves canônicas `narrative:{dim}:{pct}:{size}:{region}` com tempos de resposta `<50ms` em *Cache Hits*.
* **Degradação Suave (Graceful Fallback):** Transição automática e transparente para catálogos técnicos estáticos em caso de indisponibilidade ou limites de cota da API.
* **Controle de Taxa (Rate Limiting):** Janela deslizante de 30 req/min com limpeza proativa de memória.
* **Estatísticas Globais da Plataforma:** Endpoint `GET /api/v1/benchmark/stats` com cache em memória de 1 hora e invalidação reativa em novos envios.

---

## 🛠️ Stack Tecnológico

| Camada | Tecnologias |
| :--- | :--- |
| **Backend Framework** | Python 3.12+ • FastAPI • Pydantic v2 • Pydantic Settings |
| **Banco de Dados** | PostgreSQL 16 • SQLAlchemy 2.0 (AsyncIO) • asyncpg • Alembic |
| **LLM & IA** | Google Gemini API (Interactions API / Spec 2026) • Anthropic Claude • Ollama • HTTPX |
| **Cache e Resiliência** | In-Memory AsyncTTLCache • SlidingWindowRateLimiter • AsyncIO |
| **Testes** | Pytest • Pytest-AsyncIO • Coverage (242+ testes unitários e E2E) |

---

## 📚 Documentação do Projeto

Guias técnicos detalhados estão disponíveis no diretório `docs/`:

* 🧠 [**docs/LLM_SETUP.md**](docs/LLM_SETUP.md): Configuração de provedores LLM (Gemini, Claude, Ollama), cache e resolução de problemas.
* 🏛️ [**docs/ARCHITECTURE_PHASE2.md**](docs/ARCHITECTURE_PHASE2.md): Diagramas de sequência e fluxo de dados da Fase 2.
* 💻 [**docs/SETUP-BACK.md**](docs/SETUP-BACK.md): Instruções passo a passo para Docker, migrações com Alembic e seed inicial.

---

## 🌐 Endpoints da API

A API disponibiliza suas rotas sob o prefixo `/api/v1` com documentação interativa em **`/docs`** (Swagger UI) e **`/redoc`**:

| Método | Endpoint | Descrição |
| :---: | :--- | :--- |
| `POST` | `/api/v1/benchmark/submit` | Processa as 15 respostas, calcula scores/percentis e retorna o diagnóstico completo com IA. |
| `GET` | `/api/v1/benchmark/stats` | Retorna métricas globais agregadas da plataforma (cache de 1h com invalidação reativa). |
| `GET` | `/` | Endpoint raiz de boas-vindas e verificação de integridade (health check). |

---

## 🚀 Guia de Início Rápido

### 1. Clonar o repositório e configurar o ambiente
```bash
git clone https://github.com/No-Country-simulation/S07-26-Team-21.git
cd S07-26-Team-21/backend
python -m venv venv
```

* **Ativar ambiente virtual:**
  * Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
  * Linux/macOS: `source venv/bin/activate`

```bash
pip install -r requirements.txt
cp .env.example .env
```

### 2. Iniciar o Banco de Dados com Docker
```bash
docker compose up -d
```

### 3. Executar Migrações e Carga Inicial (Seed)
```bash
alembic upgrade head
python seed.py
```

### 4. Iniciar o Servidor de Desenvolvimento
```bash
uvicorn app.main:app --reload
```
Acesse a documentação interativa em: [http://localhost:8000/docs](http://localhost:8000/docs).

### 5. Executar a Suíte de Testes Automatizados
```bash
pytest -v
```

---

## 🔒 Privacidade e Segurança por Design

* **Pseudonimização:** Identificadores UUID v4 sem armazenamento de nomes corporativos, domínios ou endereços IP.
* **K-Anonimato:** Métricas de comparação de pares exigem uma amostragem mínima de $k \ge 3$ participantes independentes.
* **CORS Seguro:** Configuração restritiva de origens autorizadas (`BACKEND_CORS_ORIGINS`) para desenvolvimento e produção.
* **Proteção de Credenciais:** Chaves de API transmitidas via cabeçalhos HTTP dedicados (`x-goog-api-key`, `x-api-key`), excluídas de URLs e logs.
