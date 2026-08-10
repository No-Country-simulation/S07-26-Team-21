# 🌿 Guía de Convenciones de Git (Ramas y Commits)

Esta guía define el estándar de trabajo en Git para mantener un historial limpio, trazable y profesional en el repositorio del equipo.

---

## 1. 🌿 Convención para Nombres de Ramas (Branch Naming)

### 📌 Formato General
```text
<tipo>/<contexto-o-id-tarea>-<descripcion-corta>
```
* **Todo en minúsculas** (*lowercase*).
* **Separado por guiones** (*kebab-case*).
* **Sin caracteres especiales** ni espacios ni tildes.

---

### 📂 Tipos de Ramas permitidos

| Prefijo | Cuándo usarlo | Ejemplos |
| :--- | :--- | :--- |
| `feat/` | **Nueva funcionalidad**, User Story o endpoint de la API. | `feat/us1-input-schemas`<br>`feat/benchmark-calculation-engine`<br>`feat/endpoint-user-evaluation` |
| `fix/` | **Corrección de un bug** o comportamiento erróneo en `develop`. | `fix/percentile-division-by-zero`<br>`fix/cors-origins-config`<br>`fix/uuid-serialization` |
| `chore/` | **Tareas de infraestructura**, tooling, setup de DB, Docker, migraciones o dependencias (sin lógica de negocio directa). | `chore/docker-db-setup`<br>`chore/alembic-migrations`<br>`chore/db-seed`<br>`chore/update-dependencies` |
| `docs/` | **Documentación** exclusiva (READMEs, diagramas, guías en `/docs`). | `docs/database-explanation`<br>`docs/setup-backend`<br>`docs/api-swagger-guide` |
| `refactor/` | **Reestructuración de código** que no agrega features ni corrige bugs (mejora legibilidad/diseño). | `refactor/modularize-services`<br>`refactor/extract-query-helpers` |
| `test/` | **Creación o mejora de pruebas** (unitarias, integración). | `test/schemas-validation`<br>`test/benchmark-service-unit` |
| `hotfix/` | **Parches críticos directos** para producción / `main`. | `hotfix/security-jwt-leak` |

---

### 🔄 Flujo de Trabajo con Ramas
1. **Siempre partir de `develop` actualizado:**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feat/us1-input-schemas
   ```
2. **Hacer commits atómicos y claros.**
3. **Subir la rama a GitHub:**
   ```bash
   git push -u origin feat/us1-input-schemas
   ```
4. **Abrir Pull Request (PR) apuntando a `develop`** con una descripción de los cambios realizados.

---

## 2. 📝 Convención de Commits (Conventional Commits)

Adoptamos el estándar **Conventional Commits** para facilitar la lectura del historial y la trazabilidad.

### 📌 Formato General
```text
<tipo>(<alcance_opcional>): <descripción clara y en imperativo/infinitivo>
```

---

### 🏷️ Tipos de Commits y Ejemplos

#### 1. `feat:` (Nueva característica)
* Usar cuando agregas una nueva funcionalidad visible o endpoint.
* **Ejemplos:**
  * `feat(schemas): add BenchmarkRequest with Likert validation and enums`
  * `feat(api): create POST /api/v1/benchmark evaluation endpoint`
  * `feat(engine): implement calculate_percentiles service logic`

#### 2. `fix:` (Corrección de errores)
* Usar cuando solucionas un bug.
* **Ejemplos:**
  * `fix(schemas): allow null values in optional comments field`
  * `fix(db): resolve port conflict in docker compose`
  * `fix(engine): prevent zero division when industry data is empty`

#### 3. `chore:` (Mantenimiento, configs y herramientas)
* Usar para tareas de mantenimiento, dependencias, Docker, Alembic, etc.
* **Ejemplos:**
  * `chore(db): setup alembic migrations and initial tables`
  * `chore(docker): configure local postgresql container`
  * `chore: add pytest and httpx to requirements.txt`

#### 4. `docs:` (Documentación)
* Usar cuando solo tocas archivos de documentación.
* **Ejemplos:**
  * `docs: add database architecture and relationship explanation`
  * `docs(readme): add step-by-step local setup instructions`
  * `docs: add git branching and commit conventions guide`

#### 5. `refactor:` (Refactorización)
* Usar cuando cambias la estructura interna del código sin cambiar su comportamiento externo.
* **Ejemplos:**
  * `refactor(services): extract score aggregation into reusable helper`
  * `refactor(api): simplify dependency injection for db session`

#### 6. `test:` (Pruebas)
* Usar cuando añades o corriges pruebas automatizadas.
* **Ejemplos:**
  * `test(schemas): add validation unit tests for BenchmarkRequest`
  * `test(api): add integration tests for health check endpoint`

#### 7. `style:` (Estilos de código / Formateo)
* Usar para formateo, espacios en blanco, orden de imports (Black, Flake8, Ruff).
* **Ejemplos:**
  * `style: format python files with black`
  * `style: fix imports order in api routers`

---

## 💡 Reglas de Oro (Best Practices)

1. **Commits Atómicos:** Un commit debe representar un solo cambio lógico. No mezclar la creación de una feature con la corrección de un bug no relacionado.
2. **Mensajes Claros:**
   - ❌ *Malos:* `"cambios"`, `"fix"`, `"arreglando cositas"`, `"subiendo archivo"`, `"wip"`
   - ✅ *Buenos:* `"feat(schemas): add validation rules for facility_size and region"`
3. **Idioma Consistente:** Mantener el idioma acordado por el equipo (español o inglés).
4. **Pull Requests descriptivos:** Incluir qué User Story resuelve, qué se modificó y cómo probarlo.
