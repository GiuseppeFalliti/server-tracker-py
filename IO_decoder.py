"""
Decodifica della sezione I/O dei pacchetti AVL Teltonika.

I dati I/O sono organizzati in gruppi in base alla dimensione del valore:
- N1: valori da 1 byte
- N2: valori da 2 byte
- N4: valori da 4 byte
- N8: valori da 8 byte
"""

import traceback

from logger import app_logger


class IODecoder():
    """Converte il blocco I/O esadecimale in dizionari Python strutturati."""

    def __init__(self):
        self.IO_data = ""
        self.Ns_data = {}

    def ioDecoderN1(self, N1s, N1s_size):
        # Ogni coppia N1 usa 1 byte per l'ID e 1 byte per il valore.
        temp = {}
        for i in range(0, N1s_size, 4):
            id = int(N1s[i:i + 2], 16)
            val = int(N1s[i + 2:i + 4], 16)
            temp[int(id)] = val
        return temp

    def ioDecoderN2(self, N2s, N2_size):
        # Ogni coppia N2 usa 1 byte per l'ID e 2 byte per il valore.
        temp = {}
        for i in range(0, N2_size, 6):
            id = int(N2s[i:i + 2], 16)
            val = int(N2s[i + 2:i + 2 + 4], 16)
            temp[int(id)] = val
        return temp

    def ioDecoderN4(self, N4s, N4_size):
        # Ogni coppia N4 usa 1 byte per l'ID e 4 byte per il valore.
        temp = {}
        for i in range(0, N4_size, 10):
            id = int(N4s[i:i + 2], 16)
            val = int(N4s[i + 2:i + 10], 16)
            temp[int(id)] = val
        return temp

    def ioDecoderN8(self, N8s, N8_size):
        # Gestisce il gruppo dei valori a 8 byte seguendo il layout atteso
        # dall'implementazione corrente del progetto.
        temp = {}
        for i in range(0, N8_size, 10):
            if i == 0:
                id = int(N8s[i:i + 2], 16)
                val = int(N8s[i + 2:i + 18], 16)
                temp[int(id)] = val
            elif i > 18:
                id = int(N8s[i + 8:i + 10], 16)
                val = int(N8s[i + 10:i + 18], 16)
                temp[int(id)] = val
        return temp

    def dataDecoder(self, n_data):
        # Decodifica in sequenza i blocchi N1, N2, N4 e N8 presenti nel payload I/O.
        try:
            Ns_data = {}
            eventIO_ID = int(n_data[0:2], 16)
            N_Tot_io = int(n_data[2:4], 16)

            # Parsing del gruppo N1.
            n_N1 = int(n_data[4:6], 16)
            N1s_size = n_N1 * (2 + 2)
            N1s = n_data[6:6 + N1s_size]
            N1_data = self.ioDecoderN1(N1s, N1s_size)
            Ns_data['n1'] = N1_data

            # Se tutti gli I/O sono gia' contenuti in N1, si puo' terminare qui.
            if n_N1 == N_Tot_io:
                app_logger.log_system_event(
                    level="INFO",
                    event_type="io_decoder_completed_n1",
                    message="Decodifica I/O completata al gruppo N1.",
                    component="io_decoder",
                    details={"total_io": N_Tot_io},
                )
                return Ns_data

            # Parsing del gruppo N2.
            N2_start = 6 + N1s_size
            n_N2 = int(n_data[N2_start:N2_start + 2], 16)
            N2s_size = n_N2 * (2 + 4)
            N2_end = N2_start + 2 + N2s_size
            N2s = n_data[N2_start + 2: N2_end]
            N2_data = self.ioDecoderN2(N2s, N2s_size)
            Ns_data['n2'] = N2_data

            if n_N1 + n_N2 == N_Tot_io:
                app_logger.log_system_event(
                    level="INFO",
                    event_type="io_decoder_completed_n2",
                    message="Decodifica I/O completata al gruppo N2.",
                    component="io_decoder",
                    details={"total_io": N_Tot_io},
                )
                return Ns_data

            # Parsing del gruppo N4.
            N4_start = N2_end
            n_N4 = int(n_data[N4_start:N4_start + 2], 16)
            N4s_size = n_N4 * (2 + 8)
            N4_end = N4_start + 2 + N4s_size
            N4s = n_data[N4_start + 2: N4_end]
            N4_data = self.ioDecoderN4(N4s, N4s_size)
            Ns_data['n4'] = N4_data

            if n_N1 + n_N2 + n_N4 == N_Tot_io:
                app_logger.log_system_event(
                    level="INFO",
                    event_type="io_decoder_completed_n4",
                    message="Decodifica I/O completata al gruppo N4.",
                    component="io_decoder",
                    details={"total_io": N_Tot_io},
                )
                return Ns_data

            # Parsing del gruppo N8.
            N8_start = N4_end
            n_N8 = int(n_data[N8_start:N8_start + 2], 16)
            N8s_size = n_N8 * (2 + 16)
            N8_end = N8_start + 2 + N8s_size
            N8s = n_data[N8_start + 2: N8_end]
            N8_data = self.ioDecoderN8(N8s, N8s_size)
            Ns_data['n8'] = N8_data

            if n_N1 + n_N2 + n_N4 + n_N8 == N_Tot_io:
                app_logger.log_system_event(
                    level="INFO",
                    event_type="io_decoder_completed_n8",
                    message="Decodifica I/O completata al gruppo N8.",
                    component="io_decoder",
                    details={"total_io": N_Tot_io},
                )
                return Ns_data
            else:
                # Se il totale dichiarato non coincide, il pacchetto viene considerato non valido.
                app_logger.log_system_event(
                    level="ERROR",
                    event_type="io_decoder_total_mismatch",
                    message="Totale I/O dichiarato non coerente con i gruppi decodificati.",
                    component="io_decoder",
                    details={"total_io": N_Tot_io},
                )
                return -1
        except Exception as e:
            app_logger.log_system_event(
                level="ERROR",
                event_type="io_decoder_failed",
                message="Errore durante la decodifica dei blocchi I/O.",
                component="io_decoder",
                details={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "raw_io_data": n_data,
                },
            )
            return -1

    def getNSData(self):
        # Espone l'ultima struttura I/O decodificata.
        return self.Ns_data


if __name__ == '__main__':
    # Pacchetti di prova usati per testare il decoder durante lo sviluppo.
    n_data = "0009080100020103000400b301b401320033000148011d0000"
    n_data = "0105021503010101425E0F01F10000601A014E0000000000000000"
    n_data = "00060301000200b40002422dea430f1501480"
    n_data = "0211090100020103000400b300b40032003300150307432685422f171800004801184"

    d = IODecoder()
    app_logger.log_system_event(
        level="INFO",
        event_type="io_decoder_sample_decoded",
        message="Campione I/O decodificato.",
        component="io_decoder",
        details=d.dataDecoder(n_data),
    )
