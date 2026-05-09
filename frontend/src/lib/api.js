const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function fetchVehicles(signal) {
  const response = await fetch(`${API_BASE_URL}/api/vehicles`, { signal });
  if (!response.ok) {
    let detail = "";
    try {
      detail = await response.text();
    } catch {
      detail = "";
    }
    throw new Error(
      `Vehicle API request failed with status ${response.status}.${detail ? ` Response: ${detail}` : ""}`,
    );
  }

  const vehicles = await response.json();
  if (!Array.isArray(vehicles)) {
    throw new Error("Vehicle API returned an unexpected payload.");
  }

  return vehicles;
}
