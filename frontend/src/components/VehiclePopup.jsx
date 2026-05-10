function formatDate(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toLocaleDateString("it-IT")} ${date.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function formatText(value, fallback = "--") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function formatNumber(value, options = {}) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return new Intl.NumberFormat("it-IT", options).format(numericValue);
}

function formatCoordinate(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return numericValue.toFixed(5).replace(".", ",");
}

function getVehicleStatus(vehicle) {
  const referenceValue = vehicle.ts || vehicle.last_seen;
  if (!referenceValue) {
    return { label: "Offline", tone: "muted" };
  }

  const timestamp = new Date(referenceValue).getTime();
  if (Number.isNaN(timestamp)) {
    return { label: "Online", tone: "online" };
  }

  const elapsedMinutes = Math.abs(Date.now() - timestamp) / 60000;
  if (elapsedMinutes <= 30) {
    return { label: "Online", tone: "online" };
  }

  return { label: "Offline", tone: "muted" };
}

function getEngineLabel(vehicle) {
  if (vehicle.engine_type) {
    return formatText(vehicle.engine_type);
  }
  if (vehicle.motore) {
    return formatText(vehicle.motore);
  }
  return "Termico";
}

export default function VehiclePopup({ vehicle }) {
  const status = getVehicleStatus(vehicle);
  const locationLabel = [vehicle.citta, vehicle.provincia].filter(Boolean).join(" · ") || "Posizione non disponibile";
  const primaryTimestamp = formatDate(vehicle.ts || vehicle.last_seen);
  const speedValue = vehicle.speed !== null && vehicle.speed !== undefined ? formatNumber(vehicle.speed) : "--";
  const kmValue = vehicle.km !== null && vehicle.km !== undefined ? formatNumber(vehicle.km, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : "--";
  const coordinatesValue = `${formatCoordinate(vehicle.latitudine)}, ${formatCoordinate(vehicle.longitudine)}`;
  const voltageValue =
    vehicle.tensione !== null && vehicle.tensione !== undefined
      ? `${formatNumber(vehicle.tensione, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} V`
      : "--";

  return (
    <div className="vehicle-popup-card">
      <div className="vehicle-popup-card__header">
        <div className="vehicle-popup-card__symbol" aria-hidden="true">
          <span />
        </div>

        <div className="vehicle-popup-card__identity">
          <div className="vehicle-popup-card__title-row">
            <strong>{formatText(vehicle.imei)}</strong>
            <span className={`vehicle-popup-card__badge vehicle-popup-card__badge--${status.tone}`}>
              {status.label}
            </span>
          </div>

          <p className="vehicle-popup-card__subtitle">
            {formatText(vehicle.targa, `Tracker #${vehicle.id}`)}
            {vehicle.id ? ` • ${vehicle.id}` : ""}
          </p>
        </div>
      </div>

      <div className="vehicle-popup-card__meta-list">
        <p>
          <span className="vehicle-popup-card__meta-dot" aria-hidden="true" />
          {locationLabel}
        </p>
        <p>
          <span className="vehicle-popup-card__meta-dot vehicle-popup-card__meta-dot--clock" aria-hidden="true" />
          {primaryTimestamp}
        </p>
      </div>

      <div className="vehicle-popup-card__engine">
        <span className="vehicle-popup-card__engine-dot" aria-hidden="true" />
        {getEngineLabel(vehicle)}
      </div>

      <div className="vehicle-popup-card__stats">
        <article className="vehicle-popup-card__stat">
          <p className="vehicle-popup-card__stat-label">Velocita</p>
          <strong className="vehicle-popup-card__stat-value">{speedValue}</strong>
          <span className="vehicle-popup-card__stat-unit">km/h</span>
        </article>

        <article className="vehicle-popup-card__stat">
          <p className="vehicle-popup-card__stat-label">Chilometri</p>
          <strong className="vehicle-popup-card__stat-value">{kmValue}</strong>
          <span className="vehicle-popup-card__stat-unit">km</span>
        </article>

        <article className="vehicle-popup-card__stat">
          <p className="vehicle-popup-card__stat-label">Coordinate</p>
          <strong className="vehicle-popup-card__stat-copy">{coordinatesValue}</strong>
        </article>

        <article className="vehicle-popup-card__stat">
          <p className="vehicle-popup-card__stat-label">Tensione</p>
          <strong className="vehicle-popup-card__stat-copy">{voltageValue}</strong>
          <span className="vehicle-popup-card__stat-note">
            {vehicle.tensione_stato ? formatText(vehicle.tensione_stato).toUpperCase() : "STATO BATTERIA"}
          </span>
        </article>
      </div>
    </div>
  );
}
