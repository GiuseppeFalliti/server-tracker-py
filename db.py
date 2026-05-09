"""
Persistenza PostgreSQL dei dati decodificati dai tracker Teltonika.

Il modulo riceve il dizionario AVL prodotto dal decoder, normalizza i
campi utili al database e mantiene aggiornate le tabelle `tracker` e
`tracker_data`.
"""

import datetime
import os
import threading
import traceback

import psycopg2
from psycopg2.extras import RealDictCursor
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

    def upsert_tracker(self, cur, packet):
        """Restituisce l'id del tracker, creandolo se necessario."""
        cur.execute(
            'SELECT id FROM tracker WHERE "IMEI" = %s',
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
            INSERT INTO tracker ("IMEI", last_seen, station_id, model_id)
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
                    "KM" = %s
                WHERE vehicle_id = %s
                """,
                (
                    packet["longitudine"],
                    packet["latitudine"],
                    packet["ts"],
                    packet["km"],
                    tracker_id,
                ),
            )
            app_logger.log_tracker_event(
                imei=packet["imei"],
                level="INFO",
                event_type="db_tracker_data_updated",
                message="Snapshot tracker_data aggiornato.",
                component="db",
                details={"tracker_id": tracker_id},
            )
            return

        cur.execute(
            """
            INSERT INTO tracker_data (vehicle_id, longitudine, latitudine, ts, "KM")
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                tracker_id,
                packet["longitudine"],
                packet["latitudine"],
                packet["ts"],
                packet["km"],
            ),
        )
        app_logger.log_tracker_event(
            imei=packet["imei"],
            level="INFO",
            event_type="db_tracker_data_inserted",
            message="Snapshot tracker_data creato.",
            component="db",
            details={"tracker_id": tracker_id},
        )

    def normalize_packet(self, raw_data):
        """Prepara i campi nel formato atteso dallo schema SQL."""
        io = self.id_to_avl(raw_data.get("io_data", {}))

        return {
            "imei": raw_data["imei"],
            "last_seen": datetime.datetime.now(),
            "longitudine": raw_data["lon"] / 10000000,
            "latitudine": raw_data["lat"] / 10000000,
            "ts": self.resolve_packet_timestamp(raw_data),
            "km": self.extract_km(io),
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
