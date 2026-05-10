function formatDate(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("it-IT");
}

function formatText(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return value;
}

export default function VehicleSidebar({ vehicles, selectedVehicleId, onSelectVehicle }) {
  return (
    <div className="vehicle-list">
      {vehicles.map((vehicle) => {
        const isSelected = vehicle.id === selectedVehicleId;
        return (
          <button
            key={vehicle.id}
            type="button"
            className={`vehicle-card${isSelected ? " vehicle-card--selected" : ""}`}
            onClick={() => onSelectVehicle(vehicle.id)}
          >
            <div className="vehicle-card__top">
              <div>
                <p className="vehicle-card__imei">{vehicle.imei}</p>
                <p className="vehicle-card__meta">Tracker #{vehicle.id}</p>
              </div>
              <span className="vehicle-card__speed">
                {vehicle.speed !== null && vehicle.speed !== undefined ? `${vehicle.speed} km/h` : "speed --"}
              </span>
            </div>

            <dl className="vehicle-card__grid">
              <div>
                <dt>Data</dt>
                <dd>{formatDate(vehicle.ts)}</dd>
              </div>
              <div>
                <dt>Marca</dt>
                <dd>{formatText(vehicle.marca)}</dd>
              </div>
              <div>
                <dt>Modello</dt>
                <dd>{formatText(vehicle.model)}</dd>
              </div>
              <div>
                <dt>KM</dt>
                <dd>{vehicle.km ?? "--"}</dd>
              </div>
              <div>
                <dt>Citta</dt>
                <dd>{vehicle.citta ?? "--"}</dd>
              </div>
            </dl>
          </button>
        );
      })}
    </div>
  );
}
