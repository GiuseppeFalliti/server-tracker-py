import { startTransition, useEffect, useMemo, useState } from "react";
import VehicleSidebar from "./VehicleSidebar.jsx";
import VehicleMap from "./VehicleMap.jsx";
import { fetchVehicles } from "../lib/api.js";

const REFRESH_INTERVAL_MS = 15000;

function sortVehicles(vehicles) {
  return [...vehicles].sort((left, right) => {
    const rightDate = Date.parse(right.ts || right.last_seen || 0);
    const leftDate = Date.parse(left.ts || left.last_seen || 0);
    return rightDate - leftDate;
  });
}

export default function MapPage() {
  const [vehicles, setVehicles] = useState([]);
  const [selectedVehicleId, setSelectedVehicleId] = useState(null);
  const [mapFocusRequest, setMapFocusRequest] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    let isMounted = true;
    let activeController = null;

    async function loadVehicles() {
      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;
      try {
        if (isMounted && vehicles.length === 0) {
          setLoading(true);
        }
        const nextVehicles = sortVehicles(await fetchVehicles(controller.signal));
        if (!isMounted) {
          return;
        }

        startTransition(() => {
          setVehicles(nextVehicles);
          setError("");
          setLastUpdated(new Date());
        });

        setSelectedVehicleId((currentId) => {
          if (currentId && nextVehicles.some((vehicle) => vehicle.id === currentId)) {
            return currentId;
          }
          return null;
        });
      } catch (fetchError) {
        if (!isMounted || fetchError.name === "AbortError") {
          return;
        }
        setError("Impossibile caricare i veicoli dalla dashboard API.");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadVehicles();
    const intervalId = window.setInterval(loadVehicles, REFRESH_INTERVAL_MS);

    return () => {
      isMounted = false;
      activeController?.abort();
      window.clearInterval(intervalId);
    };
  }, []);

  const selectedVehicle = useMemo(
    () => vehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? null,
    [selectedVehicleId, vehicles],
  );

  function handleVehicleSelection(vehicleId) {
    setSelectedVehicleId(vehicleId);
    setMapFocusRequest((currentValue) => currentValue + 1);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <header className="sidebar__header">
          <p className="sidebar__eyebrow">Fleet Map</p>
          <h1>Veicoli in tempo reale</h1>
          <p className="sidebar__copy">
            Snapshot corrente dei tracker registrati nel database PostgreSQL.
          </p>
        </header>

        <section className="sidebar__status">
          <div>
            <span className="status-label">Veicoli</span>
            <strong>{vehicles.length}</strong>
          </div>
          <div>
            <span className="status-label">Refresh</span>
            <strong>15s</strong>
          </div>
          <div>
            <span className="status-label">Ultimo update</span>
            <strong>{lastUpdated ? lastUpdated.toLocaleTimeString("it-IT") : "--:--:--"}</strong>
          </div>
        </section>

        {error ? <div className="state-banner state-banner--error">{error}</div> : null}
        {loading ? <div className="state-banner">Caricamento veicoli...</div> : null}
        {!loading && vehicles.length === 0 ? (
          <div className="state-banner">Nessun veicolo con coordinate disponibili.</div>
        ) : null}

        <VehicleSidebar
          vehicles={vehicles}
          selectedVehicleId={selectedVehicleId}
          onSelectVehicle={handleVehicleSelection}
        />
      </aside>

      <section className="map-panel">
        <VehicleMap
          vehicles={vehicles}
          mapFocusRequest={mapFocusRequest}
          selectedVehicle={selectedVehicle}
          onSelectVehicle={handleVehicleSelection}
        />
      </section>
    </main>
  );
}
