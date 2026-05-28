import pickle
import numpy as np
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import Counter, make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

# 1. Definir el esquema de entrada con validación estricta de datos (Estilo Pure Ops)
class PredictionInput(BaseModel):
    feature_1: float = Field(..., description="Primera métrica transaccional", example=1.5)
    feature_2: float = Field(..., description="Segunda métrica transaccional", example=2.3)

# 2. Inicializar la API con metadatos profesionales
app = FastAPI(
    title="Enterprise ML Fraud Detection API",
    description="Production-grade inference service wrapped with native Kubernetes health probes.",
    version="1.0.0"
)

# 3. Cargar el artefacto de forma segura al inicializar el servicio
MODEL_PATH = "fraud_model.pkl"
try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
except Exception as e:
    raise RuntimeError(f"Error crítico al cargar el artefacto del modelo en {MODEL_PATH}: {str(e)}")

MALICIOUS_PAYLOAD_COUNTER = Counter(
    "fraud_api_malicious_payload_total",
    "Peticiones rechazadas por validación (posible fuzzing o inyección)",
    ["endpoint"],
)

app.mount("/metrics", make_asgi_app())


@app.exception_handler(RequestValidationError)
async def validation_attack_handler(request: Request, exc: RequestValidationError):
    MALICIOUS_PAYLOAD_COUNTER.labels(endpoint=request.url.path).inc()
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


# ---------------------------------------------------------
# ENDPOINTS OPERATIVOS (Para el Orquestador de Kubernetes)
# ---------------------------------------------------------

@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["Infrastructure"])
def health_check():
    """
    Liveness & Readiness Probe Nativo.
    Garantiza que el contenedor está vivo y que el modelo está cargado en memoria.
    """
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Model artifact is not loaded correctly"
        )
    return {"status": "healthy", "model_loaded": True}

# ---------------------------------------------------------
# ENDPOINTS DE NEGOCIO (Para Consumo de Microservicios)
# ---------------------------------------------------------

@app.post("/predict", status_code=status.HTTP_200_OK, tags=["Machine Learning Inference"])
def predict(payload: PredictionInput):
    """
    Endpoint de inferencia en tiempo real de alta disponibilidad.
    Recepciona el JSON, lo vectoriza y retorna la predicción pura.
    """
    try:
        # Extraer los datos validados del payload de pydantic
        input_data = np.array([[payload.feature_1, payload.feature_2]])
        
        # Ejecutar la inferencia con el modelo cargado
        prediction = model.predict(input_data)
        probability = model.predict_proba(input_data) if hasattr(model, "predict_proba") else None
        
        return {
            "prediction": int(prediction[0]),
            "fraud_probability": float(probability[0][1]) if probability is not None else None,
            "engine": "scikit-learn-production"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail= f"Execution error during inference runtime: {str(e)}"
        )


Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/healthz", "/docs", "/openapi.json", "/redoc"],
).instrument(app)