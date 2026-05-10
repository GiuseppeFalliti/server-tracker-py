import { useEffect, useMemo, useRef } from "react";
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import iconUrl from "leaflet/dist/images/marker-icon.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import VehiclePopup from "./VehiclePopup.jsx";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

const DEFAULT_CENTER = [41.9028, 12.4964];

function MapViewportController({ vehicles, selectedVehicle }) {
  const map = useMap();

  useEffect(() => {
    if (
      selectedVehicle?.latitudine !== null &&
      selectedVehicle?.latitudine !== undefined &&
      selectedVehicle?.longitudine !== null &&
      selectedVehicle?.longitudine !== undefined
    ) {
      map.setView([selectedVehicle.latitudine, selectedVehicle.longitudine], Math.max(map.getZoom(), 13), {
        animate: true,
      });
      return;
    }

    if (vehicles.length === 0) {
      map.setView(DEFAULT_CENTER, 6);
    }
  }, [map, selectedVehicle, vehicles]);

  return null;
}

export default function VehicleMap({ vehicles, selectedVehicle, onSelectVehicle }) {
  const popupRefs = useRef(new Map());

  const positions = useMemo(
    () =>
      vehicles.filter(
        (vehicle) =>
          vehicle.latitudine !== null &&
          vehicle.longitudine !== null &&
          vehicle.latitudine !== undefined &&
          vehicle.longitudine !== undefined,
      ),
    [vehicles],
  );

  useEffect(() => {
    if (!selectedVehicle) {
      return;
    }
    const popup = popupRefs.current.get(selectedVehicle.id);
    if (popup) {
      popup.openPopup();
    }
  }, [selectedVehicle]);

  return (
    <div className="map-wrap">
      <MapContainer center={DEFAULT_CENTER} zoom={6} className="fleet-map" scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapViewportController vehicles={positions} selectedVehicle={selectedVehicle} />

        {positions.map((vehicle) => (
          <Marker
            key={vehicle.id}
            position={[vehicle.latitudine, vehicle.longitudine]}
            eventHandlers={{
              click: () => onSelectVehicle(vehicle.id),
            }}
            ref={(marker) => {
              if (marker) {
                popupRefs.current.set(vehicle.id, marker);
              } else {
                popupRefs.current.delete(vehicle.id);
              }
            }}
          >
            <Popup>
              <VehiclePopup vehicle={vehicle} />
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
