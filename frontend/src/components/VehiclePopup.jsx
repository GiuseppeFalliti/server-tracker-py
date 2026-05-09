function formatDate(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("it-IT");
}

export default function VehiclePopup({ vehicle }) {
  return (
    <div className="vehicle-popup">
      <strong>{vehicle.imei}</strong>
      <p>Tracker #{vehicle.id}</p>
      <p>TS: {formatDate(vehicle.ts)}</p>
      <p>Last seen: {formatDate(vehicle.last_seen)}</p>
      <p>KM: {vehicle.km ?? "--"}</p>
      <p>Speed: {vehicle.speed ?? "--"} km/h</p>
    </div>
  );
}
