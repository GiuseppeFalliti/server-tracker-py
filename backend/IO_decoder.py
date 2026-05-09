"""
Decodifica della sezione I/O dei pacchetti AVL Teltonika Codec 8.
"""

import traceback

from logger import app_logger


class IODecoder():
    """Converte il blocco I/O binario in dizionari Python strutturati."""

    def __init__(self):
        self.IO_data = b""
        self.Ns_data = {}

    def decode_from_record(self, record_bytes, offset):
        """Decodifica la sezione I/O del record AVL partendo da un offset."""
        try:
            cursor = offset
            event_io_id = record_bytes[cursor]
            cursor += 1
            total_io_count = record_bytes[cursor]
            cursor += 1

            decoded = {
                "event_io_id": event_io_id,
                "total_io_count": total_io_count,
            }

            for group_name, value_size in (("n1", 1), ("n2", 2), ("n4", 4), ("n8", 8)):
                count = record_bytes[cursor]
                cursor += 1
                decoded[group_name] = self.decode_group(record_bytes, cursor, count, value_size)
                cursor += count * (1 + value_size)

            decoded_count = sum(len(decoded[group]) for group in ("n1", "n2", "n4", "n8"))
            if decoded_count != total_io_count:
                app_logger.log_system_event(
                    level="ERROR",
                    event_type="io_decoder_total_mismatch",
                    message="Totale I/O dichiarato non coerente con i gruppi decodificati.",
                    component="io_decoder",
                    details={
                        "total_io": total_io_count,
                        "decoded_count": decoded_count,
                    },
                )
                return -1, cursor

            app_logger.log_system_event(
                level="INFO",
                event_type="io_decoder_completed",
                message="Decodifica I/O completata.",
                component="io_decoder",
                details={
                    "event_io_id": event_io_id,
                    "total_io": total_io_count,
                    "decoded_count": decoded_count,
                },
            )
            self.Ns_data = decoded
            return decoded, cursor
        except Exception as e:
            app_logger.log_system_event(
                level="ERROR",
                event_type="io_decoder_failed",
                message="Errore durante la decodifica dei blocchi I/O.",
                component="io_decoder",
                details={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "offset": offset,
                },
            )
            return -1, offset

    def decode_group(self, record_bytes, offset, count, value_size):
        """Decodifica un gruppo I/O con valori di dimensione fissa."""
        decoded = {}
        cursor = offset
        for _ in range(count):
            avl_id = record_bytes[cursor]
            cursor += 1
            value = int.from_bytes(record_bytes[cursor:cursor + value_size], byteorder="big", signed=False)
            cursor += value_size
            decoded[avl_id] = value
        return decoded

    def dataDecoder(self, n_data):
        """Compatibilita' con il vecchio flusso: accetta bytes o stringa hex."""
        if isinstance(n_data, str):
            record_bytes = bytes.fromhex(n_data)
        else:
            record_bytes = n_data
        decoded, _ = self.decode_from_record(record_bytes, 0)
        return decoded

    def getNSData(self):
        # Espone l'ultima struttura I/O decodificata.
        return self.Ns_data


if __name__ == '__main__':
    sample_hex = "00060301000200b40002422dea430f150148"
    d = IODecoder()
    app_logger.log_system_event(
        level="INFO",
        event_type="io_decoder_sample_decoded",
        message="Campione I/O decodificato.",
        component="io_decoder",
        details=d.dataDecoder(sample_hex),
    )
