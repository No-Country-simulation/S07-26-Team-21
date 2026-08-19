# 🧠 Guía de Configuración y Arquitectura LLM (Fase 2)

Esta guía documenta la arquitectura del servicio de Inteligencia Artificial agnóstico a proveedores, su estrategia de caché, control de límites de tasa (rate limiting), degradación suave (fallbacks) y las instrucciones de setup para **Google Gemini** (especificación 2026), **Anthropic Claude** y **Ollama**.

---

## 1. 🏗️ Arquitectura Agnóstica de Proveedores LLM

El sistema implementa el **Patrón Adapter / Strategy** a través de la clase base abstracta `BaseLLMProvider` en `app/services/llm_service.py`.

```
                    ┌────────────────────────┐
                    │      LLMService        │
                    │  (Cache + RateLimiter) │
                    └───────────┬────────────┘
                                │ (Orquesta)
                                ▼
                    ┌────────────────────────┐
                    │    BaseLLMProvider     │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│GeminiProvider │       │ClaudeProvider │       │OllamaProvider │
│(Google REST)  │       │(Anthropic)    │       │(Local REST)   │
└───────────────┘       └───────────────┘       └───────────────┘
```

### ¿Cómo cambiar de proveedor?
Basta con modificar la variable de entorno `LLM_PROVIDER` en tu archivo `.env`:

```env
# Opciones disponibles: "gemini" | "claude" | "ollama"
LLM_PROVIDER=gemini
```

---

## 2. ⚡ Setup Local: Google Gemini (Interactions API / 2026 Spec)

Google Gemini está integrado mediante la API REST oficial de Google AI Studio (`v1beta`).

### Pasos de Configuración:
1. Obtener una API Key gratuita en [Google AI Studio](https://aistudio.google.com/apikey).
2. Configurar en tu archivo `backend/.env`:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=AQ.TuApiKeyDeGoogleAIStudio...
   GEMINI_MODEL=gemini-3.5-flash-lite
   LLM_TIMEOUT_SECONDS=25.0
   ```

### Particularidades Técnicas del Adaptador Gemini (`GeminiProvider`):
* **Autenticación por Header:** La clave se transmite exclusivamente en el header HTTP `x-goog-api-key`, evitando filtraciones en query strings o logs de proxies.
* **Interactions API (`/v1beta/interactions`):** Utiliza el endpoint moderno de Google con filtrado automático de pasos (`steps` tipo `thought` vs `model_output` / `modelOutput`), extrayendo únicamente la respuesta final útil.
* **Fallback a `generateContent`:** Si el endpoint de interacciones no está disponible, conmuta automáticamente a `/v1beta/models/{model}:generateContent`.
* **Modelo Recomendado:** `gemini-3.5-flash-lite` (máxima velocidad `<2s`, 500 req/día, límites permisivos).

---

## 3. 🚀 Setup Local: Ollama (100% Offline / Local)

Para desarrollo sin conexión a internet ni consumo de cuotas de API externa.

### Pasos de Configuración:
1. Instalar Ollama desde [ollama.com](https://ollama.com).
2. Descargar el modelo deseado en tu terminal:
   ```bash
   ollama run llama3:8b
   ```
3. Configurar en tu `backend/.env`:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   ```

---

## 4. 🏢 Setup Producción: Anthropic Claude (Documentado)

Preparado para despliegues empresariales de alta fidelidad y auditoría técnica.

### Pasos de Configuración en Producción:
1. Obtener clave en la consola de [Anthropic](https://console.anthropic.com/).
2. Configurar las variables en el entorno de producción:
   ```env
   LLM_PROVIDER=claude
   CLAUDE_API_KEY=sk-ant-api03-...
   CLAUDE_MODEL=claude-3-5-sonnet-20241022
   LLM_TIMEOUT_SECONDS=15.0
   ```
3. El adaptador envía los headers requeridos:
   - `x-api-key: <CLAUDE_API_KEY>`
   - `anthropic-version: 2023-06-01`
   - `content-type: application/json`

---

## 5. 🗄️ Estrategia de Caching (`AsyncTTLCache`)

Para garantizar latencias mínimas y optimizar costos de API, `LLMService` implementa una capa de caché en memoria asíncrona con **TTL de 24 horas** (86,400 segundos).

### Claves Canónicas Libres de Colisión:
Cada prompt genera una clave canónica segmentada por dimensión, rango de percentil, tamaño y región:

$$\text{Clave} = \texttt{narrative:\{dimension\}:\{rango\_percentil\}:\{facility\_size\}:\{region\}}$$

* **Ejemplo 1 (Debilidad):** `narrative:weakness:latencia:p26_50:medium:latam`
* **Ejemplo 2 (Prácticas Élite):** `narrative:practices:latencia:p76_100:medium:latam`
* **Ejemplo 3 (Recomendaciones):** `narrative:recs:latencia:p26_50:medium:latam`

### Rendimiento de Caché:
* **Cache Miss:** ~1,000ms a 3,000ms (llamada remota al LLM).
* **Cache Hit:** `< 50ms` (recuperación instantánea en memoria).

---

## 6. 🛡️ Resiliencia y Degrado Suave (Fallback Behavior)

El sistema nunca interrumpe la experiencia del usuario ni retorna errores 500 ante contingencias externas:

1. **Timeout Estricto:** Si el LLM excede `LLM_TIMEOUT_SECONDS`, se cancela la llamada asíncrona.
2. **Fallbacks Técnicos Curados:** Se inyecta una explicación técnica y recomendaciones elaboradas por expertos en Data Centers (`RECOMMENDATIONS_MAP`, `STATIC_EXPLANATION_MAP`, `STATIC_PRACTICES_MAP`).
3. **Indicador Transparente:** La respuesta incluye `llm_generated: false` para auditoría y trazabilidad.

---

## 7. ⏱️ Control de Tasa (Rate Limiting)

`SlidingWindowRateLimiter` protege el backend y las cuotas de API contra sobrecargas o ataques:
* **Configuración:** `LLM_RATE_LIMIT_PER_MINUTE=30` (30 peticiones por ventana deslizante de 60 segundos).
* **Prevención de Fugas de Memoria:** Limpieza reactiva continua de timestamps antiguos en cada evaluación.
* **Comportamiento al Exceder:** Si se supera el límite, retorna inmediatamente el fallback técnico con status `"rate_limited"` sin arrojar excepciones.

---

## 8. 🔧 Troubleshooting Común

| Síntoma | Causa Probable | Solución |
| :--- | :--- | :--- |
| `Status 404: model not found` | Modelo deprecado o no soportado en Google AI Studio. | Configurar `GEMINI_MODEL=gemini-3.5-flash-lite` en `.env`. |
| `Status 429: Too Many Requests` | Cuota gratuita saturada por ráfaga instantánea. | Usar `gemini-3.5-flash-lite` (límite más alto) o esperar 60s. |
| `Timeout (>25.0s)` | Conexión lenta o modelo de razonamiento profundo. | Incrementar `LLM_TIMEOUT_SECONDS=30.0` en `.env`. |
| `ValueError: API key not set` | Variable `GEMINI_API_KEY` ausente o vacía. | Definir la clave en `backend/.env` y reiniciar el servidor. |
