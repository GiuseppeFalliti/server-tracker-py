"""
API HTTP dedicata alla dashboard veicoli.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db import TrackerRepository
from logger import app_logger


app = FastAPI(title="Tracker Dashboard API", version="1.0.0")
repository = TrackerRepository()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/vehicles")
def get_vehicles():
    try:
        vehicles = repository.get_vehicle_snapshots()
        app_logger.log_system_event(
            level="INFO",
            event_type="api_vehicles_served",
            message="Lista veicoli restituita alla dashboard.",
            component="api",
            details={"vehicle_count": len(vehicles)},
        )
        return vehicles
    except Exception as exc:
        app_logger.log_system_event(
            level="ERROR",
            event_type="api_vehicles_failed",
            message="Errore durante il recupero dei veicoli per la dashboard.",
            component="api",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Unable to fetch vehicles.") from exc
