# 🚀 Guía de Configuración Local (Backend)

Sigue estos pasos para levantar el entorno de desarrollo local con la base de datos y la carga inicial de datos.

## 1. Variables de Entorno
Crea un archivo `.env` en la raíz de la carpeta `backend` (puedes copiar el `.env.example` si existe) y asegúrate de tener esta configuración para evitar conflictos con instalaciones locales de Postgres:

```env
POSTGRES_SERVER=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=benchmark_password_2026
POSTGRES_DB=benchmark_engine
```

## 2. Levantar la Base de Datos (Docker)
En la terminal (parado en la carpeta `backend`), ejecuta:
```bash
docker compose up -d
```
*Esto descargará la imagen de PostgreSQL y levantará el contenedor exponiendo el puerto 5433.*

## 3. Entorno Virtual y Dependencias
Crea y activa tu entorno virtual, luego instala las dependencias:
```bash
# En Windows (Git Bash):
python -m venv venv
source venv/Scripts/activate

# Instalar dependencias
pip install -r requirements.txt
```

## 4. Crear las Tablas (Alembic)
Para ejecutar las migraciones y crear las tablas en tu Docker:
```bash
alembic upgrade head
```

## 5. Poblar la Base de Datos (Seed)
Para inyectar los benchmarks iniciales de la industria, ejecuta el script de seed:
```bash
python seed.py
```
*Si ves el mensaje de éxito, tu base de datos ya está lista con los 35 benchmarks.*

## 6. ¿Cómo ver la Base de Datos?
Para visualizar y manipular los datos de Docker, recomendamos usar **DBeaver** (gratis) o **TablePlus**. 

Los datos de conexión locales son:
- **Motor:** PostgreSQL
- **Host:** localhost
- **Puerto:** 5433
- **Base de Datos:** benchmark_engine
- **Usuario:** postgres
- **Contraseña:** benchmark_password_2026