# ==========================================
# STAGE 1: Compilación y dependencias (Builder)
# ==========================================
FROM python:3.10-slim AS builder

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar ruedas de C
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar y compilar dependencias en un espacio aislado
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# STAGE 2: Entorno de ejecución final (Production)
# ==========================================
FROM python:3.10-slim AS runner

WORKDIR /app

# Configurar variables de entorno de Python seguras para contenedores
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

# Copiar únicamente las librerías instaladas desde el stage anterior (Cero basura)
COPY --from=builder /root/.local /root/.local

# Copiar el código fuente y el artefacto del modelo
COPY main.py .
COPY fraud_model.pkl .

# Exponer el puerto de producción de la API
EXPOSE 8000

# Ejecución segura con Uvicorn sintonizado para producción
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]