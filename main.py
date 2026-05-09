"""
Server TCP multicliente per tracker Teltonika FMBXXX.

Il server accetta le connessioni dei dispositivi, riceve l'IMEI,
risponde con l'ack di handshake e poi elabora i pacchetti AVL
confermando al tracker il numero di record ricevuti.
"""

import binascii
import datetime
import socket
import threading
import time
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
            accept_con_mes = '\x01'
            conn.send(accept_con_mes.encode('utf-8'))
            app_logger.log_tracker_event(
                imei=imei,
                level="INFO",
                event_type="tracker_handshake_accepted",
                message="Handshake IMEI completato.",
                component="server",
                client_addr=addr,
            )

            while True:
                data = conn.recv(1024)
                if not data:
                    app_logger.log_tracker_event(
                        imei=imei,
                        level="INFO",
                        event_type="tracker_socket_closed",
                        message="Il tracker ha chiuso la connessione dati.",
                        component="server",
                        client_addr=addr,
                    )
                    break

                vars = {}
                recieved = self.decoder(data)
                raw_hex = recieved.decode('utf-8')
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
                vars = avl_decoder.decodeAVL(recieved)
                if vars == -1:
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
                        "packet": vars,
                        "record_count": vars["no_record_i"],
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
                    details={"record_count": vars["no_record_i"]},
                )

                # Il protocollo richiede la conferma del numero di record accettati.
                resp = self.mResponse(vars['no_record_i'])
                time.sleep(30)
                conn.send(resp)
                app_logger.log_tracker_event(
                    imei=imei,
                    level="INFO",
                    event_type="tracker_ack_sent",
                    message="ACK inviato al tracker.",
                    component="server",
                    client_addr=addr,
                    details={
                        "record_count": vars["no_record_i"],
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
                imei_data = conn.recv(1024)
                if imei_data:
                    imei = self.extract_imei(imei_data)
                    app_logger.log_tracker_event(
                        imei=imei,
                        level="INFO",
                        event_type="tracker_imei_received",
                        message="IMEI tracker ricevuto dal server TCP.",
                        component="server",
                        client_addr=addr,
                        details={"raw_imei": imei_data.decode('utf-8', errors='replace')},
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

    def decoder(self, raw):
        # Converte il frame binario in stringa esadecimale per il decoder AVL.
        decoded = binascii.hexlify(raw)
        return decoded

    def extract_imei(self, imei_data):
        decoded_imei = imei_data.decode('utf-8', errors='replace')
        if "\x0f" in decoded_imei:
            return decoded_imei.split("\x0f", 1)[1]
        return decoded_imei.strip()

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
