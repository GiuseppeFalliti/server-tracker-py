"""
Decodifica della sezione I/O dei pacchetti AVL Teltonika Codec 8 e 8E.
"""

import traceback

from logger import app_logger


class IODecoder():
    """Converte il blocco I/O binario in dizionari Python strutturati."""

    def __init__(self):
        self.IO_data = b""
        self.Ns_data = {}

    def decode_from_record(self, record_bytes, offset, codec_id=0x08):
        """Decodifica la sezione I/O del record AVL partendo da un offset."""
        try:
            cursor = offset
            is_extended = codec_id == 0x8E
            counter_size = 2 if is_extended else 1
            id_size = 2 if is_extended else 1

            event_io_id = self.read_uint(record_bytes, cursor, id_size)
            cursor += id_size
            total_io_count = self.read_uint(record_bytes, cursor, counter_size)
            cursor += counter_size

            decoded = {
                "event_io_id": event_io_id,
                "total_io_count": total_io_count,
            }

            for group_name, value_size in (("n1", 1), ("n2", 2), ("n4", 4), ("n8", 8)):
                count = self.read_uint(record_bytes, cursor, counter_size)
                cursor += counter_size
                group_decoded, cursor = self.decode_group(
                    record_bytes,
                    cursor,
                    count,
                    value_size,
                    id_size,
                )
                decoded[group_name] = group_decoded

            if is_extended:
                nx_count = self.read_uint(record_bytes, cursor, counter_size)
                cursor += counter_size
                nx_decoded, cursor = self.decode_variable_group(
                    record_bytes,
                    cursor,
                    nx_count,
                    id_size,
                    counter_size,
                )
                decoded["nx"] = nx_decoded
            else:
                decoded["nx"] = {}

            decoded_count = sum(len(decoded[group]) for group in ("n1", "n2", "n4", "n8", "nx"))
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

    def decode_group(self, record_bytes, offset, count, value_size, id_size):
        """Decodifica un gruppo I/O con valori di dimensione fissa."""
        decoded = {}
        cursor = offset
        for _ in range(count):
            avl_id = self.read_uint(record_bytes, cursor, id_size)
            cursor += id_size
            value = int.from_bytes(record_bytes[cursor:cursor + value_size], byteorder="big", signed=False)
            cursor += value_size
            decoded[avl_id] = value
        return decoded, cursor

    def decode_variable_group(self, record_bytes, offset, count, id_size, length_size):
        """Decodifica il gruppo NX del Codec 8E con valori a lunghezza variabile."""
        decoded = {}
        cursor = offset
        for _ in range(count):
            avl_id = self.read_uint(record_bytes, cursor, id_size)
            cursor += id_size
            value_length = self.read_uint(record_bytes, cursor, length_size)
            cursor += length_size
            value_bytes = record_bytes[cursor:cursor + value_length]
            if len(value_bytes) != value_length:
                raise ValueError("Valore NX incompleto nel record Codec 8E.")
            cursor += value_length
            decoded[avl_id] = value_bytes.hex()
        return decoded, cursor

    def read_uint(self, record_bytes, offset, size):
        """Legge un intero unsigned di dimensione fissa dal buffer indicato."""
        value_bytes = record_bytes[offset:offset + size]
        if len(value_bytes) != size:
            raise ValueError("Buffer insufficiente durante la lettura dei campi I/O.")
        return int.from_bytes(value_bytes, byteorder="big", signed=False)

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
