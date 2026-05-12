"""
Persistenza PostgreSQL dei dati decodificati dai tracker Teltonika.

Il modulo riceve il dizionario AVL prodotto dal decoder, normalizza i
campi utili al database e mantiene aggiornate le tabelle `tracker` e
`tracker_data`.
"""

import datetime
import os
import re
import threading
import traceback

import psycopg2
import reverse_geocoder as rg
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv

from avlMatcher import avlIdMatcher
from logger import app_logger


load_dotenv()

avl_match = avlIdMatcher()


class TrackerRepository:
    """Gestisce il salvataggio dei pacchetti AVL su PostgreSQL."""

    def __init__(self):
        self.db_config = {
            "host": os.getenv("PGHOST"),
            "dbname": os.getenv("PGDATABASE"),
            "user": os.getenv("PGUSER"),
            "password": os.getenv("PGPASSWORD"),
            "port": os.getenv("PGPORT", "5432"),
        }
        self.connection = None
        self.lock = threading.Lock()
        self.city_cache = {}

    def save_tracker_packet(self, raw_data):
        """Salva o aggiorna tracker e snapshot telemetrico corrente."""
        if not raw_data.get("imei"):
            raise ValueError("IMEI mancante nel pacchetto AVL.")

        normalized_data = self.normalize_packet(raw_data)

        with self.lock:
            conn = self.get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    tracker_id = self.upsert_tracker(cur, normalized_data)
                    self.upsert_tracker_data(cur, tracker_id, normalized_data)
                conn.commit()
                app_logger.log_tracker_event(
                    imei=normalized_data["imei"],
                    level="INFO",
                    event_type="db_transaction_committed",
                    message="Transazione PostgreSQL completata.",
                    component="db",
                    details={"tracker_id": tracker_id},
                )
            except Exception:
                conn.rollback()
                app_logger.log_tracker_event(
                    imei=normalized_data["imei"],
                    level="ERROR",
                    event_type="db_transaction_rolled_back",
                    message="Rollback PostgreSQL eseguito dopo un errore.",
                    component="db",
                    details={"traceback": traceback.format_exc()},
                )
                raise

    def get_vehicle_snapshots(self):
        """Restituisce i veicoli con posizione corrente per la dashboard web."""
        with self.lock:
            conn = self.get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT
                            tracker.id,
                            tracker.imei AS imei,
                            tracker.last_seen,
                            tracker.station_id,
                            tracker.model_id,
                            tracker.marca,
                            tracker.model,
                            tracker_data.longitudine,
                            tracker_data.latitudine,
                            tracker_data.ts,
                            tracker_data.km AS km,
                            tracker_data.io_elements
                        FROM tracker
                        INNER JOIN tracker_data
                            ON tracker_data.vehicle_id = tracker.id
                        WHERE tracker_data.longitudine IS NOT NULL
                          AND tracker_data.latitudine IS NOT NULL
                        ORDER BY COALESCE(tracker_data.ts, tracker.last_seen) DESC, tracker.id ASC
                        """
                    )
                    rows = cur.fetchall()
            except Exception:
                app_logger.log_system_event(
                    level="ERROR",
                    event_type="db_vehicle_query_failed",
                    message="Query dashboard veicoli fallita.",
                    component="db",
                    details={"traceback": traceback.format_exc()},
                )
                raise

        vehicles = [self.serialize_vehicle_snapshot(row) for row in rows]
        app_logger.log_system_event(
            level="INFO",
            event_type="db_vehicle_query_completed",
            message="Query dashboard veicoli completata.",
            component="db",
            details={"vehicle_count": len(vehicles)},
        )
        return vehicles

    def get_connection(self):
        """Apre la connessione al primo uso e la riapre se chiusa."""
        self.validate_config()

        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(**self.db_config)
            app_logger.log_system_event(
                level="INFO",
                event_type="db_connection_opened",
                message="Connessione PostgreSQL aperta.",
                component="db",
                details={"host": self.db_config["host"], "dbname": self.db_config["dbname"]},
            )
        return self.connection

    def validate_config(self):
        missing = [key for key, value in self.db_config.items() if not value]
        if missing:
            app_logger.log_system_event(
                level="ERROR",
                event_type="db_config_invalid",
                message="Configurazione PostgreSQL incompleta.",
                component="db",
                details={"missing_keys": missing},
            )
            raise RuntimeError(
                "Configurazione PostgreSQL incompleta. Variabili mancanti: "
                + ", ".join(missing)
            )

    def serialize_vehicle_snapshot(self, row):
        """Normalizza una riga SQL nel formato JSON atteso dal frontend."""
        io_elements = row.get("io_elements") or {}
        speed = self.parse_numeric_value(io_elements.get("speed"))
        latitudine = float(row["latitudine"]) if row.get("latitudine") is not None else None
        longitudine = float(row["longitudine"]) if row.get("longitudine") is not None else None
        return {
            "id": row["id"],
            "imei": row["imei"],
            "last_seen": self.serialize_datetime(row.get("last_seen")),
            "latitudine": latitudine,
            "longitudine": longitudine,
            "citta": self.resolve_city(latitudine, longitudine),
            "ts": self.serialize_datetime(row.get("ts")),
            "km": row.get("km"),
            "speed": speed,
            "marca": row.get("marca"),
            "model": row.get("model"),
            "station_id": row.get("station_id"),
            "model_id": row.get("model_id"),
        }

    def serialize_datetime(self, value):
        """Converte datetime Python in stringa ISO 8601."""
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        return str(value)

    def parse_numeric_value(self, value):
        """Converte in intero i valori numerici ricevuti dal JSONB, con fallback a None."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def resolve_city(self, latitudine, longitudine):
        """Ricava il nome della citta dalle coordinate con cache in memoria."""
        if latitudine is None or longitudine is None:
            return None

        cache_key = (round(latitudine, 5), round(longitudine, 5))
        if cache_key in self.city_cache:
            return self.city_cache[cache_key]

        try:
            result = rg.search(cache_key)
            city = result[0].get("name") if result else None
        except Exception:
            city = None
            app_logger.log_system_event(
                level="ERROR",
                event_type="reverse_geocoder_failed",
                message="Impossibile risolvere la citta dalle coordinate del tracker.",
                component="db",
                details={
                    "latitudine": latitudine,
                    "longitudine": longitudine,
                    "traceback": traceback.format_exc(),
                },
            )

        self.city_cache[cache_key] = city
        return city

    def upsert_tracker(self, cur, packet):
        """Restituisce l'id del tracker, creandolo se necessario."""
        cur.execute(
            "SELECT id FROM tracker WHERE imei = %s",
            (packet["imei"],),
        )
        tracker_row = cur.fetchone()

        if tracker_row:
            cur.execute(
                'UPDATE tracker SET last_seen = %s WHERE id = %s',
                (packet["last_seen"], tracker_row["id"]),
            )
            app_logger.log_tracker_event(
                imei=packet["imei"],
                level="INFO",
                event_type="db_tracker_updated",
                message="Tracker esistente aggiornato.",
                component="db",
                details={"tracker_id": tracker_row["id"]},
            )
            return tracker_row["id"]

        cur.execute(
            """
            INSERT INTO tracker (imei, last_seen, station_id, model_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (packet["imei"], packet["last_seen"], None, None),
        )
        tracker_id = cur.fetchone()["id"]
        app_logger.log_tracker_event(
            imei=packet["imei"],
            level="INFO",
            event_type="db_tracker_inserted",
            message="Nuovo tracker inserito.",
            component="db",
            details={"tracker_id": tracker_id},
        )
        return tracker_id

    def upsert_tracker_data(self, cur, tracker_id, packet):
        """Mantiene una sola riga di telemetria per ogni tracker."""
        cur.execute(
            "SELECT id FROM tracker_data WHERE vehicle_id = %s",
            (tracker_id,),
        )
        tracker_data_row = cur.fetchone()

        if tracker_data_row:
            cur.execute(
                """
                UPDATE tracker_data
                SET longitudine = %s,
                    latitudine = %s,
                    ts = %s,
                    km = %s,
                    io_elements = %s
                WHERE vehicle_id = %s
                """,
                (
                    packet["longitudine"],
                    packet["latitudine"],
                    packet["ts"],
                    packet["km"],
                    Json(packet["io_elements"]),
                    tracker_id,
                ),
            )
            app_logger.log_tracker_event(
                imei=packet["imei"],
                level="INFO",
                event_type="db_tracker_data_updated",
                message="Snapshot tracker_data aggiornato.",
                component="db",
                details={
                    "tracker_id": tracker_id,
                    "io_elements_keys": len(packet["io_elements"]),
                    "has_raw_io": packet["has_raw_io"],
                    "has_named_io": packet["has_named_io"],
                },
            )
            return

        cur.execute(
            """
            INSERT INTO tracker_data (vehicle_id, longitudine, latitudine, ts, km, io_elements)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                packet["longitudine"],
                packet["latitudine"],
                packet["ts"],
                packet["km"],
                Json(packet["io_elements"]),
            ),
        )
        app_logger.log_tracker_event(
            imei=packet["imei"],
            level="INFO",
            event_type="db_tracker_data_inserted",
            message="Snapshot tracker_data creato.",
            component="db",
            details={
                "tracker_id": tracker_id,
                "io_elements_keys": len(packet["io_elements"]),
                "has_raw_io": packet["has_raw_io"],
                "has_named_io": packet["has_named_io"],
            },
        )

    def normalize_packet(self, raw_data):
        """Prepara i campi nel formato atteso dallo schema SQL."""
        named_io = self.id_to_avl(raw_data.get("io_data", {}))
        flat_named_io = self.flatten_named_io(named_io)
        flat_raw_io = self.flatten_raw_io(raw_data.get("io_data", {}))
        io_elements = self.build_io_elements(raw_data, flat_named_io)

        return {
            "imei": raw_data["imei"],
            "last_seen": datetime.datetime.now(),
            "longitudine": raw_data["lon"] / 10000000,
            "latitudine": raw_data["lat"] / 10000000,
            "ts": self.resolve_packet_timestamp(raw_data),
            "km": self.extract_km(named_io),
            "io_elements": io_elements,
            "has_raw_io": bool(flat_raw_io),
            "has_named_io": bool(flat_named_io),
        }

    def resolve_packet_timestamp(self, raw_data):
        """Usa il timestamp AVL, con fallback a quello locale del server."""
        unix_ms = raw_data.get("d_time_unix")
        if unix_ms:
            return datetime.datetime.fromtimestamp(unix_ms / 1000)

        local_time = raw_data.get("d_time_local")
        if local_time:
            return datetime.datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S")

        return datetime.datetime.now()

    def extract_km(self, io_data):
        """Cerca il chilometraggio in una serie di chiavi AVL note."""
        km_keys = (
            "Total Odometer",
            "Total Mileage",
            "Total Mileage (counted)",
            "Trip Odometer",
            "OBD OEM Total Mileage",
        )

        for key in km_keys:
            value = io_data.get(key)
            if value is not None:
                return value
        return None

    def id_to_avl(self, data):
        """Traduce gli ID I/O numerici in etichette leggibili."""
        formatted = {}
        for group in data.values():
            for avl_id, value in group.items():
                avl_info = avl_match.getAvlInfo(str(avl_id))
                if isinstance(avl_info, dict):
                    formatted[avl_info["name"]] = value
        return formatted

    def flatten_raw_io(self, data):
        """Appiattisce i gruppi I/O grezzi in chiavi stabili."""
        flattened = {}
        for group_name, group_values in data.items():
            for avl_id, value in group_values.items():
                flattened[f"io_raw_{group_name}_{avl_id}"] = value
        return flattened

    def flatten_named_io(self, named_io):
        """Appiattisce gli elementi I/O nominati con chiavi normalizzate."""
        flattened = {}
        for name, value in named_io.items():
            normalized_name = self.normalize_io_key(name)
            flattened[f"io_name_{normalized_name}"] = value
        return flattened

    def build_io_elements(self, raw_data, flat_named_io):
        """Costruisce l'oggetto JSONB piatto con i campi AVL utili alla dashboard."""
        avl_fields = {
            "imei": raw_data.get("imei"),
            "sys_time": raw_data.get("sys_time"),
            "codecid": raw_data.get("codecid"),
            "no_record_i": raw_data.get("no_record_i"),
            "no_record_e": raw_data.get("no_record_e"),
            "crc-16": raw_data.get("crc-16"),
            "d_time_unix": raw_data.get("d_time_unix"),
            "d_time_local": raw_data.get("d_time_local"),
            "priority": raw_data.get("priority"),
            "lon": raw_data.get("lon"),
            "lat": raw_data.get("lat"),
            "alt": raw_data.get("alt"),
            "angle": raw_data.get("angle"),
            "satellites": raw_data.get("satellites"),
            "speed": raw_data.get("speed"),
        }
        avl_fields.update(flat_named_io)
        return avl_fields

    def normalize_io_key(self, value):
        """Rende stabili e sicure le chiavi dei campi I/O nominati."""
        normalized = value.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")


if __name__ == "__main__":
    sample = {
        "imei": "352093081429150",
        "d_time_unix": 1609621190808,
        "d_time_local": "2021-01-03 02:29:50",
        "lon": 801065150,
        "lat": 130466366,
        "io_data": {
            "n4": {
                16: 123456
            }
        },
    }

    repo = TrackerRepository()
    app_logger.log_system_event(
        level="INFO",
        event_type="db_sample_normalized",
        message="Esempio di pacchetto normalizzato.",
        component="db",
        imei=sample["imei"],
        details=repo.normalize_packet(sample),
    )
