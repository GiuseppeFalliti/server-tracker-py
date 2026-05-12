"""
Decoder completo dei pacchetti AVL Teltonika Codec 8 e 8E su TCP.
"""

import datetime

from IO_decoder import IODecoder
from logger import app_logger


io = IODecoder()


class avlDecoder():
    """Parsa un frame Codec 8/8E TCP e restituisce records e metadati."""

    def __init__(self):
        self.raw_data = b""

    def decodeAVL(self, data):
        """Decodifica un frame TCP Teltonika Codec 8 o 8E."""
        try:
            self.raw_data = data
            if len(data) < 12:
                return self.invalid_packet("Frame troppo corto.", {"frame_length": len(data)})

            preamble = data[:4]
            if preamble != b"\x00\x00\x00\x00":
                return self.invalid_packet("Preamble non valido.", {"preamble_hex": preamble.hex()})

            data_field_length = int.from_bytes(data[4:8], byteorder="big")
            expected_length = 8 + data_field_length + 4
            if len(data) != expected_length:
                return self.invalid_packet(
                    "Lunghezza frame non coerente con data field length.",
                    {
                        "data_field_length": data_field_length,
                        "frame_length": len(data),
                        "expected_length": expected_length,
                    },
                )

            codec_id = data[8]
            if codec_id not in (0x08, 0x8E):
                return self.invalid_packet("Codec ID non supportato.", {"codec_id": codec_id})

            record_count_1 = data[9]
            payload_end = 8 + data_field_length
            record_count_2 = data[payload_end - 1]
            if record_count_1 != record_count_2:
                return self.invalid_packet(
                    "Number of Data mismatch.",
                    {
                        "record_count_1": record_count_1,
                        "record_count_2": record_count_2,
                    },
                )

            crc_received = int.from_bytes(data[payload_end:payload_end + 4], byteorder="big")
            crc_calculated = self.crc16_ibm(data[8:payload_end])
            if crc_calculated != (crc_received & 0xFFFF):
                return self.invalid_packet(
                    "CRC-16/IBM non valido.",
                    {
                        "crc_received": crc_received,
                        "crc_received_low": crc_received & 0xFFFF,
                        "crc_calculated": crc_calculated,
                    },
                )

            cursor = 10
            records = []
            for _ in range(record_count_1):
                record, cursor = self.parse_record(data, cursor)
                if record == -1:
                    return -1
                records.append(record)

            if cursor != payload_end - 1:
                return self.invalid_packet(
                    "Offset finale record non coerente con payload AVL.",
                    {
                        "cursor": cursor,
                        "payload_end": payload_end - 1,
                    },
                )

            primary_record = records[0]
            packet = {
                "codec_id": codec_id,
                "record_count": record_count_1,
                "record_count_confirmed": record_count_2,
                "crc_received": crc_received,
                "crc_valid": True,
                "records": records,
                "primary_record": self.to_legacy_record(primary_record, codec_id, record_count_1, record_count_2, crc_received),
            }

            app_logger.log_system_event(
                level="INFO",
                event_type="decoder_packet_decoded",
                message="Frame AVL decodificato con successo.",
                component="decoder",
                details={
                    "codec_id": codec_id,
                    "record_count": record_count_1,
                    "crc_valid": True,
                },
            )
            return packet
        except Exception as e:
            return self.invalid_packet(
                "Eccezione durante la decodifica del frame AVL.",
                {
                    "error": str(e),
                },
            )

    def parse_record(self, data, offset):
        """Decodifica un singolo record AVL."""
        try:
            cursor = offset
            timestamp_unix_ms = int.from_bytes(data[cursor:cursor + 8], byteorder="big")
            cursor += 8
            priority = data[cursor]
            cursor += 1
            lon = int.from_bytes(data[cursor:cursor + 4], byteorder="big", signed=True)
            cursor += 4
            lat = int.from_bytes(data[cursor:cursor + 4], byteorder="big", signed=True)
            cursor += 4
            alt = int.from_bytes(data[cursor:cursor + 2], byteorder="big", signed=False)
            cursor += 2
            angle = int.from_bytes(data[cursor:cursor + 2], byteorder="big", signed=False)
            cursor += 2
            satellites = data[cursor]
            cursor += 1
            speed = int.from_bytes(data[cursor:cursor + 2], byteorder="big", signed=False)
            cursor += 2

            io_data, cursor = io.decode_from_record(data, cursor, codec_id=self.raw_data[8])
            if io_data == -1:
                return -1, offset

            record = {
                "sys_time": self.getDateTime(),
                "d_time_unix": timestamp_unix_ms,
                "d_time_local": self.unixtoLocal(timestamp_unix_ms),
                "priority": priority,
                "lon": lon,
                "lat": lat,
                "alt": alt,
                "angle": angle,
                "satellites": satellites,
                "speed": speed,
                "io_event_id": io_data["event_io_id"],
                "io_total_count": io_data["total_io_count"],
                "io_data": {
                    "n1": io_data["n1"],
                    "n2": io_data["n2"],
                    "n4": io_data["n4"],
                    "n8": io_data["n8"],
                    "nx": io_data.get("nx", {}),
                },
            }
            return record, cursor
        except Exception as e:
            app_logger.log_system_event(
                level="ERROR",
                event_type="decoder_record_failed",
                message="Errore durante la decodifica di un record AVL.",
                component="decoder",
                details={
                    "error": str(e),
                    "offset": offset,
                },
            )
            return -1, offset

    def to_legacy_record(self, record, codec_id, record_count_1, record_count_2, crc_received):
        """Adatta il record primario al formato atteso dal resto del progetto."""
        packet = record.copy()
        packet.update(
            {
                "codecid": codec_id,
                "no_record_i": record_count_1,
                "no_record_e": record_count_2,
                "crc-16": crc_received,
            }
        )
        return packet

    def invalid_packet(self, message, details):
        app_logger.log_system_event(
            level="ERROR",
            event_type="decoder_invalid_packet",
            message=message,
            component="decoder",
            details=details,
        )
        return -1

    def crc16_ibm(self, payload):
        """Calcola il CRC-16/IBM (ARC) sul payload indicato."""
        crc = 0x0000
        for byte in payload:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def getDateTime(self):
        return datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def unixtoLocal(self, unix_time):
        time = datetime.datetime.fromtimestamp(unix_time / 1000)
        return f"{time:%Y-%m-%d %H:%M:%S}"

    def getRawData(self):
        return self.raw_data


if __name__ == "__main__":
    sample_hex = (
        "00000000000004d2081d00000176ccb789480000000000000000000000000000000000060301000200b40002422dea430f150148"
        "000000000000000176ccb69ee80000000000000000000000000000000000060301000200b40002422de8430f150148000000000000"
        "000176ccb5b4880000000000000000000000000000000000060301000200b40002422de6430f160148000000000000000176ccb4ca"
        "280000000000000000000000000000000000060301000200b40002422de6430f130148000000000000000176ccb3dfc80000000000"
        "000000000000000000000000060301000200b40002422de6430f160148000000000000000176ccb2f5680000000000000000000000"
        "000000000000060301000200b40002422de6430f110148000000000000000176ccb20b080000000000000000000000000000000000"
        "060301000200b40002422de4430f110148000000000000000176cc96f1880000000000000000000000000000000000040301000200"
        "b400000148000000000000000176cc9607280000000000000000000000000000000000040301000200b40000014800000000000000"
        "0176cc951cc80000000000000000000000000000000000040301000200b400000148000000000000000176cc943268000000000000"
        "0000000000000000000000040301000200b400000148000000000000000176cc934808000000000000000000000000000000000004"
        "0301000200b400000148000000000000000176cc925da80000000000000000000000000000000000040301000200b4000001480000"
        "00000000000176cc9173480000000000000000000000000000000000040301000200b400000148000000000000000176cc900be800"
        "00000000000000000000000000000000040301000200b400000148000000000000000176cc8f96b800000000000000000000000000"
        "00000000040301000200b400000148000000000000000176cc8eac580000000000000000000000000000000000040301000200b400"
        "000148000000000000000176cc8d4cc80200000000000000000000000000000002040301000200b400000148000000000000000176"
        "cc8d06780000000000000000000000000000000000040301000200b400000148000000000000000176cc8c1c180000000000000000"
        "000000000000000000040301000200b400000148000000000000000176cc8b31b80000000000000000000000000000000000040301"
        "000200b400000148000000000000000176cc8a47580000000000000000000000000000000000040301000200b40000014800000000"
        "0000000176cc895cf80000000000000000000000000000000000040301000200b400000148000000000000000176cc887298000000"
        "0000000000000000000000000000040301000200b400000148000000000000000176cc878838000000000000000000000000000000"
        "0000040301000200b400000148000000000000000176cc869dd80000000000000000000000000000000000040301000200b4000001"
        "48000000000000000176cc85b3780000000000000000000000000000000000040301000200b400000148000000000000000176cc84"
        "c9180000000000000000000000000000000000040301000200b400000148000000000000000176cc83deb800000000000000000000"
        "00000000000000040301000200b40000014800000000001d000027ca"
    )
    decoder = avlDecoder()
    result = decoder.decodeAVL(bytes.fromhex(sample_hex))
    app_logger.log_system_event(
        level="INFO",
        event_type="decoder_sample_decoded",
        message="Campione AVL decodificato.",
        component="decoder",
        details=result,
    )
