"""
Classe per codificare messaggi nei codec supportati da Teltonika.

In questo file e' implementata la costruzione del codec 12, usato per
inviare comandi testuali ai tracker tramite GPRS/SMS.
"""

import binascii
import libscrc

from crcControl import crcControl
from toBytes import hexToBytes


crc = crcControl()


class msgEncoder():
    """Costruisce il frame Teltonika a partire da un comando testuale."""

    def __init__(self):
        self.raw_msg = ''

    def msgToCodec12(self, msg, cmd_type):
        # I primi 4 byte del frame Teltonika restano sempre a zero.
        self.zero_bytes = '00000000'

        # Struttura del pacchetto codec 12:
        # codec id, quantita' comandi, tipo comando, lunghezza, payload, quantita' finale, CRC.
        self.codec_id = '0C'
        self.cmd_quant_1 = '01'
        self.cmd_type = '05' if cmd_type == 'cmd' else '06'
        self.cmd_size = len(msg).to_bytes(4, byteorder='big').hex()
        self.cmd_byte_size = len(msg)
        self.cmd = binascii.hexlify(msg.encode('utf-8')).decode()
        self.cmd_quant_2 = '01'
        self.data_size = int(
            (
                len(self.codec_id) +
                len(self.cmd_quant_1) +
                len(self.cmd_type) +
                len(self.cmd_size) +
                len(self.cmd) +
                len(self.cmd_quant_2)
            ) / 2
        ).to_bytes(4, byteorder='big').hex()

        # Il CRC copre solo la parte dati successiva ai quattro byte iniziali a zero.
        crc_data = self.codec_id + self.cmd_quant_1 + self.cmd_type + self.cmd_size + self.cmd + self.cmd_quant_2
        self.crc = crc.crcGen(crc_data)['hex']

        # Calcola la dimensione totale in byte del frame completo.
        msg_byte_size = 4 + 4 + int(
            (
                len(self.codec_id) +
                len(self.cmd_quant_1) +
                len(self.cmd_type) +
                len(self.cmd_size) +
                len(self.cmd) +
                len(self.cmd_quant_2)
            ) / 2
        ) + 4

        # Compone il messaggio finale in esadecimale e poi lo converte in bytes.
        self.complete_msg_hex = (
            self.zero_bytes +
            self.data_size +
            self.codec_id +
            self.cmd_quant_1 +
            self.cmd_type +
            self.cmd_size +
            self.cmd +
            self.cmd_quant_2 +
            self.crc
        )
        msg_int = int(self.complete_msg_hex, 16)
        self.complete_msg_byte = hexToBytes(msg_int, msg_byte_size)

        print("full msg size", msg_byte_size)
        print("msg hex:", self.complete_msg_hex)
        print("msg byte", self.complete_msg_byte)

        return self.complete_msg_byte

    def msgCodec12(self):
        # Restituisce una rappresentazione descrittiva dei segmenti del pacchetto generato.
        print(
            self.zero_bytes,
            self.data_size,
            self.codec_id,
            self.cmd_quant_1,
            self.cmd_type,
            self.cmd_size,
            self.cmd,
            self.cmd_quant_2,
            self.crc
        )
        data = {
            "zero_bytes": {
                "data": self.zero_bytes,
                "byte_size": 4
            },
            "data_size": {
                "data": self.data_size,
                "byte_size": 4
            },
            "codec_id": {
                "data": self.codec_id,
                "byte_size": 1
            },
            "quantity_1": {
                "data": self.cmd_quant_1,
                "byte_size": 1
            },
            "cmd_type": {
                "data": self.cmd_type,
                "byte_size": 1
            },
            "cmd_size": {
                "data": self.cmd_size,
                "byte_size": 1
            },
            "cmd": {
                "data": self.cmd,
                "byte_size": self.cmd_byte_size
            },
            "quantity_2": {
                "data": self.cmd_quant_2,
                "byte_size": 1
            },
            "crc_16": {
                "data": self.crc
            }
        }
        return data


if __name__ == '__main__':
    # Esempio di comando codec 12 inviabile al tracker.
    a = msgEncoder()
    msg = 'setdigout 1 60'
    msg = 'setdigout 10'
    cmd_type = 'cmd'
    a.msgToCodec12(msg, cmd_type)
