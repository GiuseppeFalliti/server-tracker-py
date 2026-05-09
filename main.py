"""
Server TCP multicliente per tracker Teltonika FMBXXX.

Il server accetta le connessioni dei dispositivi, riceve l'IMEI,
risponde con l'ack di handshake e poi elabora i pacchetti AVL
confermando al tracker il numero di record ricevuti.
"""

import datetime
import socket
import threading
import traceback

from avlDecoder import avlDecoder
from db import TrackerRepository
from logger import app_logger


avl_decoder = avlDecoder()
tracker_repository = TrackerRepository()


class TCPServer():
    """Incapsula il socket server e il dialogo con ciascun tracker connesso."""

    def __init__(self, port):
        self.port = port
        self.running = True
        # Socket TCP IPv4 con opzioni utili a riavvio rapido e bassa latenza.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(1)
        self.sock.bind(('', self.port))
        app_logger.log_system_event(
            level="INFO",
            event_type="server_socket_bound",
            message="Socket TCP inizializzato e bind completato.",
            component="server",
            details={"port": self.port},
        )

    def tcpServer(self):
        # Avvia l'ascolto e crea un thread separato per ogni tracker.
        self.sock.listen()
        app_logger.log_system_event(
            level="INFO",
            event_type="server_listening",
            message="Server TCP in ascolto.",
            component="server",
            details={"port": self.port},
        )
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    app_logger.log_system_event(
                        level="ERROR",
                        event_type="server_accept_failed",
                        message="Errore durante accept() del socket server.",
                        component="server",
                        details={"traceback": traceback.format_exc()},
                    )
                    raise
                break

            thread = threading.Thread(
                target=self.handle_client,
                args=(conn, addr),
                daemon=True,
            )
            thread.start()
            app_logger.log_system_event(
                level="INFO",
                event_type="client_thread_started",
                message="Thread client avviato.",
                component="server",
                client_addr=addr,
                details={"active_connections": threading.active_count() - 1},
            )

    def Communicator(self, conn, imei, addr):
        try:
            # Il byte 0x01 comunica al tracker che l'IMEI e' stato accettato.
            conn.send(b"\x01")
            app_logger.log_tracker_event(
                imei=imei,
                level="INFO",
                event_type="tracker_handshake_accepted",
                message="Handshake IMEI completato.",
                component="server",
                client_addr=addr,
            )

            while True:
                data = self.recv_avl_packet(conn)
                if data is None:
                    app_logger.log_tracker_event(
                        imei=imei,
                        level="INFO",
                        event_type="tracker_socket_closed",
                        message="Il tracker ha chiuso la connessione dati.",
                        component="server",
                        client_addr=addr,
                    )
                    break

                raw_hex = data.hex()
                app_logger.log_tracker_event(
                    imei=imei,
                    level="INFO",
                    event_type="tracker_packet_received",
                    message="Pacchetto AVL ricevuto dal tracker.",
                    component="server",
                    client_addr=addr,
                    details={"raw_hex": raw_hex, "bytes_received": len(data)},
                )

                # Decodifica il pacchetto AVL e associa l'IMEI gia' letto.
                decoded_packet = avl_decoder.decodeAVL(data)
                if decoded_packet == -1:
                    app_logger.log_tracker_event(
                        imei=imei,
                        level="ERROR",
                        event_type="tracker_packet_invalid",
                        message="Pacchetto AVL non valido ricevuto dal tracker.",
                        component="server",
                        client_addr=addr,
                        details={"raw_hex": raw_hex},
                    )
                    raise ValueError("Pacchetto AVL non valido ricevuto dal tracker.")

                vars = decoded_packet["primary_record"].copy()
                vars['imei'] = imei
                app_logger.log_tracker_event(
                    imei=imei,
                    level="INFO",
                    event_type="tracker_packet_decoded",
                    message="Pacchetto AVL decodificato con successo.",
                    component="server",
                    client_addr=addr,
                    details={
                        "raw_hex": raw_hex,
                        "packet": decoded_packet,
                        "record_count": decoded_packet["record_count"],
                    },
                )

                # Persiste il pacchetto prima di confermare al tracker.
                tracker_repository.save_tracker_packet(vars)
                app_logger.log_tracker_event(
                    imei=imei,
                    level="INFO",
                    event_type="tracker_packet_persisted",
                    message="Pacchetto tracker salvato su PostgreSQL.",
                    component="server",
                    client_addr=addr,
                    details={"record_count": decoded_packet["record_count"]},
                )

                # Il protocollo richiede la conferma del numero di record accettati.
                resp = self.mResponse(decoded_packet["record_count"])
                conn.send(resp)
                app_logger.log_tracker_event(
                    imei=imei,
                    level="INFO",
                    event_type="tracker_ack_sent",
                    message="ACK inviato al tracker.",
                    component="server",
                    client_addr=addr,
                    details={
                        "record_count": decoded_packet["record_count"],
                        "ack_hex": resp.hex(),
                    },
                )
        except Exception as e:
            app_logger.log_tracker_event(
                imei=imei,
                level="ERROR",
                event_type="tracker_packet_processing_failed",
                message="Errore durante l'elaborazione del pacchetto tracker.",
                component="server",
                client_addr=addr,
                details={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
        finally:
            app_logger.log_tracker_event(
                imei=imei,
                level="INFO",
                event_type="tracker_communication_ended",
                message="Comunicazione TCP con il tracker terminata.",
                component="server",
                client_addr=addr,
            )

    def handle_client(self, conn, addr):
        # Prima fase del protocollo: ricezione dell'IMEI del tracker.
        app_logger.log_system_event(
            level="INFO",
            event_type="client_connected",
            message="Nuova connessione TCP accettata.",
            component="server",
            client_addr=addr,
        )
        connected = True
        while connected:
            try:
                imei = self.read_imei(conn)
                if imei:
                    app_logger.log_tracker_event(
                        imei=imei,
                        level="INFO",
                        event_type="tracker_imei_received",
                        message="IMEI tracker ricevuto dal server TCP.",
                        component="server",
                        client_addr=addr,
                        details={"imei_length": len(imei)},
                    )
                    self.Communicator(conn, imei, addr)
                    connected = False
                else:
                    app_logger.log_system_event(
                        level="INFO",
                        event_type="client_disconnected_before_imei",
                        message="Client disconnesso prima dell'invio IMEI.",
                        component="server",
                        client_addr=addr,
                    )
                    break
            except Exception as e:
                app_logger.log_system_event(
                    level="ERROR",
                    event_type="client_connection_failed",
                    message="Errore durante la gestione iniziale della connessione client.",
                    component="server",
                    client_addr=addr,
                    details={
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                conn.close()
                break
        try:
            conn.close()
        except OSError:
            pass

    def recv_exact(self, conn, size):
        """Legge esattamente `size` byte dal socket o ritorna None se chiuso."""
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = conn.recv(remaining)
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def read_imei(self, conn):
        """Legge l'IMEI nel formato Teltonika: 2 byte length + ASCII."""
        length_bytes = self.recv_exact(conn, 2)
        if length_bytes is None:
            return None
        imei_length = int.from_bytes(length_bytes, byteorder="big")
        if imei_length <= 0:
            raise ValueError("Lunghezza IMEI non valida.")
        imei_bytes = self.recv_exact(conn, imei_length)
        if imei_bytes is None:
            return None
        return imei_bytes.decode("ascii")

    def recv_avl_packet(self, conn):
        """Legge un frame AVL TCP completo secondo la lunghezza dichiarata."""
        header = self.recv_exact(conn, 8)
        if header is None:
            return None
        data_field_length = int.from_bytes(header[4:8], byteorder="big")
        remaining = self.recv_exact(conn, data_field_length + 4)
        if remaining is None:
            return None
        return header + remaining

    def getDateTime(self):
        # Timestamp locale del server, utile per eventuali log operativi.
        return datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def mResponse(self, data):
        # L'ack deve essere inviato come intero big-endian a 4 byte.
        return data.to_bytes(4, byteorder='big')

    def shutdown(self):
        """Chiude il socket server e sblocca il loop di accept."""
        if not self.running:
            return

        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        app_logger.log_system_event(
            level="INFO",
            event_type="server_shutdown",
            message="Server TCP arrestato.",
            component="server",
            details={"port": self.port},
        )


if __name__ == '__main__':
    # Porta TCP di ascolto del server.
    port = 5001
    data = TCPServer(port)
    try:
        data.tcpServer()
    except KeyboardInterrupt:
        app_logger.log_system_event(
            level="INFO",
            event_type="server_keyboard_interrupt",
            message="Interruzione richiesta da tastiera.",
            component="server",
        )
    finally:
        data.shutdown()
