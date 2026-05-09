const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export async function fetchVehicles(signal) {
  const response = await fetch(`${API_BASE_URL}/api/vehicles`, { signal });
  if (!response.ok) {
    throw new Error(`Vehicle API request failed with status ${response.status}.`);
  }

  const vehicles = await response.json();
  if (!Array.isArray(vehicles)) {
    throw new Error("Vehicle API returned an unexpected payload.");
  }

  return vehicles;
}
