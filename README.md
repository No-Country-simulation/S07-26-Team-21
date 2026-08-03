# S07-26-Team-21

🚀 Motor de Benchmark de Madurez Operativa para Data Centers
Este proyecto consiste en la construcción del núcleo lógico para una herramienta de diagnóstico de industria que permite a los operadores de centros de datos medir su nivel de madurez operativa y eficiencia en comparación con el resto del sector.

📝 Contexto del Problema
Los centros de datos modernos enfrentan el desafío de la "stranded capacity": energía y enfriamiento que se pagan y están encendidos, pero que no se aprovechan porque las capas de infraestructura y cargas de trabajo no se coordinan entre sí.

Este sistema permite a un operador completar un test anónimo de menos de 10 minutos y obtener su posición relativa (percentil) frente a líderes como Google (PUE 1.09) y el promedio global de la industria (PUE 1.56).

📊 Las 5 Dimensiones de Medición
El benchmark evalúa la madurez a través de 15 indicadores clave divididos en:
Visibilidad Cross-layer: Unificación de vistas entre energía, enfriamiento y servidores.

Atribución de Fricción: Identificación de interfaces donde se pierde más capacidad.

Latencia de Coordinación: Velocidad de ajuste de infraestructura ante cambios en la carga.

Auto-cuantificación: Conocimiento numérico exacto de la capacidad desperdiciada.

Bloqueantes: Barreras financieras, tecnológicas o humanas para la optimización.

🛠️ Stack Tecnológico
Para garantizar la escalabilidad y privacidad, el equipo definió el siguiente stack:
Backend: Python con FastAPI para la gestión de endpoints y lógica de negocio.

Base de Datos: PostgreSQL para el almacenamiento de semillas industriales y resultados anónimos.

Frontend: React + TypeScript para una interfaz de usuario dinámica tipo "Wizard".

Lógica de Datos: Prototipado en Python para el cálculo de percentiles y rebalanceo dinámico.

🔐 Privacidad por Diseño (Anonymization)
Siguiendo las mejores prácticas de la industria, el sistema implementa:
Pseudonimización: Se utiliza UUID como identificador único en lugar de nombres de empresas o IPs.
Generalización de Datos: Los valores sensibles se almacenan en rangos para evitar la re-identificación del operador.
Dataset Agregado: Los datos individuales alimentan una fuente primaria global sin exponer la identidad de los participantes.

📈 Lógica del Motor (Kernel)
El motor de scoring transforma las respuestas (escala 1 a 5) en información de negocio:
Normalización: Las dimensiones se llevan a una escala de 0 a 100 para visualización.

Rebalanceo Dinámico: Se aplica Shrinkage Bayesiano para que, al inicio, el sistema dependa de datos públicos y migre gradualmente hacia datos reales del sector conforme crece la base de datos.

👥 Equipo de Desarrollo
Tomas Quiroz: Data Science / Colombia UTC-5.
Luis Calegari: Backend (Lead API) / Argentina UTC-3.
Geraldin Nuñez: Frontend / Peru UTC-5.
Pedro Vallejos: Backend / Argentina UTC-3.
Jovany Alvarez: Backend / Mexico UTC-6.
José Lugo: Backend / Chile UTC-4.
Brenis Hernandez: Data Analyst / Mexico UTC-6.
Juan Alvarez: Data Analyst / Argentina UTC-3.
