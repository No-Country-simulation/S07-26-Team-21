# S07-26-Team-21

# 🚀 S07-26-Team-21

# Motor de Benchmark de Madurez Operativa para Data Centers

Una plataforma diseñada para evaluar el nivel de madurez operativa de centros de datos mediante un sistema de benchmarking basado en indicadores de eficiencia, coordinación y utilización de infraestructura.

El objetivo es proporcionar a los operadores un diagnóstico rápido y anónimo que les permita conocer su posición relativa respecto de la industria e identificar oportunidades de optimización.

---

## 📖 Descripción del Proyecto

Los centros de datos modernos enfrentan un problema cada vez más relevante: la **Stranded Capacity**, es decir, recursos de energía y refrigeración que permanecen disponibles y generan costos, pero que no pueden aprovecharse debido a la falta de coordinación entre la infraestructura física y las cargas de trabajo.

Este proyecto desarrolla el **núcleo lógico** de un motor de benchmarking que permite:

* Completar una evaluación en menos de **10 minutos**.
* Obtener un puntaje de madurez operativa.
* Comparar los resultados con referencias de la industria.
* Identificar áreas de mejora para incrementar la eficiencia del centro de datos.

Como referencia, el sistema considera indicadores públicos como:

* 🟢 **Google:** PUE ≈ **1.09**
* 🔵 **Promedio mundial:** PUE ≈ **1.56**

---

# 📊 Dimensiones de Evaluación

La madurez operativa se mide mediante **15 indicadores** distribuidos en cinco dimensiones principales.

## 1. 🔍 Visibilidad Cross-Layer

Evalúa el nivel de integración entre las distintas capas del centro de datos:

* Energía
* Refrigeración
* Infraestructura IT
* Servidores

---

## 2. ⚙️ Atribución de Fricción

Identifica los puntos donde se pierde mayor capacidad operativa debido a problemas de coordinación entre sistemas.

---

## 3. ⏱️ Latencia de Coordinación

Mide la velocidad con la que la infraestructura responde a cambios en la demanda de las cargas de trabajo.

---

## 4. 📈 Auto-Cuantificación

Determina el nivel de conocimiento que posee la organización sobre:

* Capacidad instalada
* Capacidad utilizada
* Recursos desperdiciados

---

## 5. 🚧 Bloqueantes

Analiza las principales barreras que dificultan la optimización operativa, entre ellas:

* Financieras
* Tecnológicas
* Organizacionales
* Humanas

---

# 🛠️ Stack Tecnológico

| Componente             | Tecnología         |
| ---------------------- | ------------------ |
| Backend                | Python + FastAPI   |
| Frontend               | React + TypeScript |
| Base de Datos          | PostgreSQL         |
| Procesamiento de Datos | Python             |

---

# 🧠 Funcionamiento del Motor de Scoring

El sistema transforma las respuestas del cuestionario (escala de **1 a 5**) en métricas comparables mediante un proceso compuesto por:

### Normalización

Cada dimensión se convierte a una escala de **0 a 100**, facilitando la visualización y comparación de resultados.

### Rebalanceo Dinámico

Inicialmente el benchmark utiliza información pública disponible.

A medida que aumenta la cantidad de evaluaciones realizadas, el sistema reduce progresivamente el peso de los datos públicos y construye un benchmark basado en información real, agregada y anonimizada de la industria.

---

# 🔒 Privacidad por Diseño

La plataforma fue diseñada siguiendo principios de **Privacy by Design**.

### Pseudonimización

Cada evaluación utiliza un **UUID** como identificador único, evitando almacenar nombres de empresas o direcciones IP.

### Generalización de Datos

La información sensible se almacena en rangos o categorías para minimizar el riesgo de reidentificación.

### Dataset Agregado

Los resultados individuales se incorporan a una base estadística global completamente anonimizada, utilizada exclusivamente para mejorar la calidad del benchmark.

---

# 📌 Objetivos

* Medir la madurez operativa de un Data Center.
* Detectar oportunidades de mejora.
* Comparar el desempeño con el resto de la industria.
* Construir un benchmark dinámico basado en datos reales.
* Mantener la privacidad de todos los participantes.

---

# 👥 Equipo de Desarrollo

| Integrante       | Rol              | País                   |
| ---------------- | ---------------- | ---------------------- |
| Tomas Quiroz     | Data Science     | 🇨🇴 Colombia (UTC-5)  |
| Luis Calegari    | Backend Lead API | 🇦🇷 Argentina (UTC-3) |
| Geraldin Nuñez   | Frontend         | 🇵🇪 Perú (UTC-5)      |
| Pedro Vallejos   | Backend          | 🇦🇷 Argentina (UTC-3) |
| Jovany Alvarez   | Backend          | 🇲🇽 México (UTC-6)    |
| José Lugo        | Backend          | 🇨🇱 Chile (UTC-4)     |
| Brenis Hernandez | Data Analyst     | 🇲🇽 México (UTC-6)    |
| Juan Alvarez     | Data Analyst     | 🇦🇷 Argentina (UTC-3) |

---

# 🎯 Estado del Proyecto

🚧 **En desarrollo**

Actualmente el equipo trabaja en la implementación del motor de benchmarking, la API REST, la interfaz de usuario y el algoritmo de cálculo de percentiles para ofrecer una herramienta escalable, segura y orientada a la toma de decisiones basada en datos.

