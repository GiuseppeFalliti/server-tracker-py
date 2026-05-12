# Server Tracker Py

Server TCP in Python per tracker Teltonika con:

- parsing `Codec 8 TCP`
- parsing `Codec 8 Extended (8E) TCP`
- persistenza PostgreSQL
- API FastAPI per la dashboard
- frontend React + Leaflet per la mappa veicoli
- logging JSON strutturato

## Architettura

Il progetto e' diviso in due parti principali:

1. `backend/`
   - riceve i pacchetti TCP dei tracker
   - decodifica i record AVL
   - salva lo stato corrente su PostgreSQL
   - espone l'API `/api/vehicles` per la dashboard
2. `frontend/`
   - interroga periodicamente l'API
   - mostra i veicoli in lista e su mappa
   - centra la mappa solo su selezione esplicita del veicolo

## Flusso end-to-end

1. Il tracker apre una connessione TCP verso il server.
2. Invia l'IMEI nel formato Teltonika `2 byte length + ASCII`.
3. Il server risponde `0x01` se l'handshake viene accettato.
4. Il tracker invia un frame AVL `Codec 8 TCP` oppure `Codec 8 Extended (8E) TCP`.
5. Il server valida `preamble`, `codec id`, `record count` e `CRC-16/IBM`.
6. Il decoder estrae il `primary_record` e i blocchi I/O.
7. `backend/db.py` aggiorna:
   - `tracker`
   - `tracker_data`
8. La dashboard legge i dati da `GET /api/vehicles`.
9. Il frontend aggiorna mappa e lista ogni 15 secondi.

## Funzionalita'

- listener TCP multi-client per tracker Teltonika
- parser completo `Codec 8 TCP`
- supporto `Codec 8 Extended (0x8E)` con I/O estesi e NX variabile
- supporto a record multipli nello stesso frame
- mapping degli AVL ID tramite `avlIds.json`
- salvataggio telemetria corrente su PostgreSQL
- dashboard HTTP con FastAPI
- frontend React con mappa Leaflet
- reverse geocoding delle coordinate con `reverse_geocoder`
- campi dashboard: `citta`, `marca`, `model`, `km`, `speed`
- log JSON Lines globali e per singolo tracker

## Struttura del progetto

```text
server_py/
|- backend/
|  |- api_main.py
|  |- api_server.py
|  |- avlDecoder.py
|  |- avlIds.json
|  |- avlMatcher.py
|  |- db.py
|  |- Dialogo_TCP_tracker.md
|  |- ecosystem.config.js
|  |- IO_decoder.py
|  |- logger.py
|  |- main.py
|  |- msgEncoder.py
|  |- PM2_GUIDE.md
|  |- requirements.txt
|  \- start-pm2-server.cmd
|- frontend/
|  |- package.json
|  |- src/
|  |  |- App.jsx
|  |  |- main.jsx
|  |  |- styles.css
|  |  \- components/
|  |     |- MapPage.jsx
|  |     |- VehicleMap.jsx
|  |     |- VehiclePopup.jsx
|  |     \- VehicleSidebar.jsx
|  \- vite.config.js
\- README.md
```

## Backend

### Componenti principali

- `backend/main.py`
  - entry point del server TCP
  - handshake IMEI
  - ricezione frame AVL
  - persistenza su PostgreSQL
- `backend/avlDecoder.py`
  - parser completo del frame `Codec 8 TCP`
  - supporto al frame `Codec 8 Extended (8E) TCP`
- `backend/IO_decoder.py`
  - parsing delle sezioni I/O `N1`, `N2`, `N4`, `N8`
- `backend/db.py`
  - normalizzazione dati
  - update di `tracker` e `tracker_data`
  - serializzazione dei veicoli per la dashboard
- `backend/api_server.py`
  - API FastAPI della dashboard
- `backend/api_main.py`
  - avvio Uvicorn su `0.0.0.0:8000`

### API disponibili

#### `GET /api/health`

Ritorna lo stato del servizio API e le origin CORS abilitate.

#### `GET /api/vehicles`

Restituisce i veicoli con coordinate disponibili.

Campi attuali del payload:

- `id`
- `imei`
- `last_seen`
- `latitudine`
- `longitudine`
- `citta`
- `ts`
- `km`
- `speed`
- `marca`
- `model`
- `station_id`
- `model_id`

Esempio:

```json
[
  {
    "id": 1,
    "imei": "352093081429150",
    "last_seen": "2026-05-09T21:31:48.558672+02:00",
    "latitudine": 41.9028,
    "longitudine": 12.4964,
    "citta": "Rome",
    "ts": "2026-05-09T21:30:48.558672+02:00",
    "km": 128450.0,
    "speed": 42,
    "marca": "Fiat",
    "model": "Ducato",
    "station_id": 1,
    "model_id": 101
  }
]
```

### Database PostgreSQL

La configurazione viene letta da `backend/.env`.

Esempio:

```env
PGHOST=localhost
PGDATABASE=tracker_db
PGUSER=postgres
PGPASSWORD=your_password
PGPORT=5432
```

Tabelle attese:

#### `tracker`

- `id`
- `imei`
- `last_seen`
- `station_id`
- `model_id`
- `marca`
- `model`

#### `tracker_data`

- `id`
- `vehicle_id`
- `longitudine`
- `latitudine`
- `ts`
- `km`
- `io_elements`

## Frontend

La dashboard e' costruita con React, Vite e Leaflet.

### Librerie principali

- `react`
- `react-dom`
- `leaflet`
- `react-leaflet`

### Comportamento della mappa

- la mappa usa OpenStreetMap come `TileLayer` base
- al refresh pagina non apre popup automaticamente
- al refresh pagina non fa auto-zoom sui veicoli
- cliccando un veicolo nella lista o un marker, la mappa centra il punto selezionato
- il popup del veicolo selezionato viene aperto sulla mappa

### Sidebar veicoli

La lista laterale mostra:

- `imei`
- timestamp `ts`
- `marca`
- `model`
- `km`
- `citta`
- `speed`

## Installazione

### Backend

Da `backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Su Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Frontend

Da `frontend/`:

```bash
npm install
```

## Avvio locale

### Server TCP tracker

Da `backend/`:

```bash
python main.py
```

### API dashboard

Da `backend/`:

```bash
python api_main.py
```

### Frontend

Da `frontend/`:

```bash
npm run dev
```

## Build frontend

Da `frontend/`:

```bash
npm run build
```

La build viene scritta in `frontend/dist/`.

## Deploy e riavvio servizi

Dopo una modifica backend:

1. aggiornare il codice sulla macchina target
2. installare o aggiornare le dipendenze:

```bash
pip install -r requirements.txt
```

3. riavviare il servizio API o il process manager usato

Se usi `systemd`:

```bash
sudo systemctl restart tracker-dashboard-api
sudo systemctl status tracker-dashboard-api
```

Se usi PM2 su Windows, consulta [backend/PM2_GUIDE.md](backend/PM2_GUIDE.md).

Dopo una modifica frontend:

```bash
npm install
npm run build
```

## Logging

Il progetto scrive log JSON Lines in:

- `backend/logs/system.json`
- `backend/logs/<IMEI>/YYYY-MM-DD.json`

I log PM2, quando usato, stanno in:

- `backend/pm2-logs/tracker-tcp-server-out.log`
- `backend/pm2-logs/tracker-tcp-server-error.log`
- `backend/pm2-logs/tracker-dashboard-api-out.log`
- `backend/pm2-logs/tracker-dashboard-api-error.log`

## Documenti utili

- [backend/Dialogo_TCP_tracker.md](backend/Dialogo_TCP_tracker.md)
- [backend/PM2_GUIDE.md](backend/PM2_GUIDE.md)
