# Server TCP Tracker Teltonika

Server TCP in Python per tracker Teltonika con parser completo `Codec 8 TCP`, persistenza su PostgreSQL e logging JSON strutturato per server e dispositivi.

## Panoramica

Il progetto implementa un listener TCP pensato per rimanere attivo h24 e gestire il flusso reale dei tracker Teltonika:

1. ricezione dell'`IMEI handshake`
2. risposta di accettazione `0x01`
3. ricezione del frame AVL completo
4. validazione del frame `Codec 8 TCP`
5. decodifica dei record AVL e dei blocchi I/O
6. salvataggio su PostgreSQL
7. invio dell'ACK finale con il `record count`
8. scrittura dei log JSON globali e per tracker

## Funzionalita'

- ascolto TCP continuo sulla porta configurata nel codice
- parsing completo `Codec 8 TCP`
- lettura IMEI nel formato `2 byte length + ASCII IMEI`
- lettura frame-aware dal socket con `recv_exact`
- validazione di `preamble`, `codec id`, `record count` e `CRC-16/IBM`
- supporto ai record multipli nello stesso frame AVL
- parsing dei blocchi I/O `N1`, `N2`, `N4`, `N8`
- salvataggio su PostgreSQL delle informazioni correnti del tracker
- salvataggio del payload AVL normalizzato in `tracker_data.io_elements`
- logging JSON Lines globale e per singolo tracker
- esecuzione persistente con PM2 su Windows

## Flusso di funzionamento

1. Il tracker apre una connessione TCP verso il server.
2. Il server legge i primi 2 byte della lunghezza IMEI.
3. Il server legge esattamente i byte ASCII dell'IMEI.
4. Il server accetta l'handshake inviando `0x01`.
5. Il server legge il frame AVL TCP completo:
   - `preamble`
   - `data field length`
   - `codec id`
   - `number of data 1`
   - record AVL
   - `number of data 2`
   - `CRC`
6. Il decoder valida:
   - `preamble = 00000000`
   - `codec id = 0x08`
   - coerenza tra i due `number of data`
   - `CRC-16/IBM`
7. Il decoder estrae tutti i record del frame e costruisce:
   - `records`
   - `record_count`
   - `crc_valid`
   - `primary_record`
8. Il server salva su database il `primary_record` del pacchetto, mantenendo nei log e nel decoder la visibilita' del batch completo.
9. Il server invia al tracker l'ACK finale come intero big-endian a 4 byte con il numero di record accettati.

## Protocollo Codec 8 TCP

### IMEI handshake

Il tracker si presenta con un frame iniziale composto da:

```text
[2 byte lunghezza IMEI][IMEI ASCII]
```

Esempio logico:

```text
000F333532303933303831343239313530
```

- `000F`: lunghezza IMEI = 15
- il resto e' l'IMEI ASCII

Se l'IMEI viene accettato, il server risponde con:

```text
01
```

### AVL frame

Dopo l'handshake, il tracker invia un frame AVL TCP nel formato:

```text
[preamble][data field length][codec id][number of data 1][AVL data ...][number of data 2][CRC]
```

Significato dei campi principali:

- `preamble`: sempre `00000000`
- `data field length`: lunghezza del blocco dati dal `codec id` fino al secondo `number of data`
- `codec id`: per questo progetto deve essere `0x08`
- `number of data 1`: numero record dichiarato all'inizio del payload
- `number of data 2`: numero record dichiarato alla fine del payload
- `CRC`: checksum del payload verificato con `CRC-16/IBM`

### ACK finale

Dopo la validazione e l'elaborazione del frame, il server risponde con:

```text
000000<record_count>
```

Esempio per `29` record accettati:

```text
0000001D
```

## Struttura del progetto

```text
server_py/
|- main.py
|- db.py
|- logger.py
|- avlDecoder.py
|- IO_decoder.py
|- avlMatcher.py
|- avlIds.json
|- msgEncoder.py
|- ecosystem.config.js
|- start-pm2-server.cmd
|- README.md
|- PM2_GUIDE.md
|- .env
|- .env.example
|- logs/
|- pm2-home/
\- pm2-logs/
```

## Componenti principali

### `main.py`

E' l'entry point del server TCP. Si occupa di:

- apertura del socket server
- ascolto e accettazione delle connessioni
- lettura dell'IMEI con parsing binario rigoroso
- lettura del frame AVL completo tramite `recv_exact`
- invocazione del decoder `Codec 8 TCP`
- persistenza su PostgreSQL
- invio dell'ACK finale al tracker
- logging degli eventi di rete e di protocollo

### `avlDecoder.py`

Implementa il parser completo del frame `Codec 8 TCP`.

Funzioni principali:

- verifica del `preamble`
- verifica del `codec id`
- verifica della coerenza del `record count`
- verifica del `CRC-16/IBM`
- parsing sequenziale dei record AVL
- gestione di record multipli nello stesso frame

Il decoder restituisce una struttura con:

- `records`
- `record_count`
- `record_count_confirmed`
- `crc_received`
- `crc_valid`
- `primary_record`

### `IO_decoder.py`

Decodifica la sezione I/O del record AVL secondo la struttura ufficiale del `Codec 8`:

- `event_io_id`
- `total_io_count`
- gruppo `N1`
- gruppo `N2`
- gruppo `N4`
- gruppo `N8`

Ogni gruppo viene interpretato con dimensioni valore coerenti con la specifica Teltonika.

### `db.py`

Gestisce la connessione PostgreSQL e aggiorna le tabelle applicative:

- `tracker`
- `tracker_data`

Persistenza principale:

- `IMEI`
- `last_seen`
- `longitudine`
- `latitudine`
- `ts`
- `KM`
- `io_elements` (`jsonb`)

La colonna `io_elements` contiene il payload AVL normalizzato:

- campi principali del record
- blocchi I/O raw appiattiti come `io_raw_*`
- blocchi I/O nominati come `io_name_*`

### `logger.py`

Scrive eventi JSON Lines in modo strutturato e thread-safe:

- `logs/system.json` per il log globale del server
- `logs/<IMEI>/YYYY-MM-DD.json` per il log giornaliero di ogni tracker

### `avlMatcher.py`

Converte gli AVL ID numerici in nomi leggibili usando `avlIds.json`.

## Database PostgreSQL

Il progetto legge la configurazione da `.env`.

Esempio:

```env
PGHOST=localhost
PGDATABASE=your_database_name
PGUSER=postgres
PGPASSWORD=your_password
PGPORT=5432
```

### Tabelle attese

#### `tracker`

- `id`
- `IMEI`
- `last_seen`
- `station_id`
- `model_id`

#### `tracker_data`

- `id`
- `vehicle_id`
- `longitudine`
- `latitudine`
- `ts`
- `KM`
- `io_elements`

## Sistema di logging

Il logging e' strutturato in formato JSON Lines.

### Log globale

Percorso:

```text
logs/system.json
```

Contiene eventi di:

- startup e shutdown del server
- nuove connessioni TCP
- ricezione IMEI
- ricezione dei frame AVL
- esito del decode
- persistenza su database
- invio ACK
- errori di rete
- errori applicativi
- errori di framing
- mismatch del `record count`
- `CRC` invalido

### Log per tracker

Percorso:

```text
logs/<IMEI>/YYYY-MM-DD.json
```

Ogni riga e' un evento JSON autonomo. I campi tipici sono:

- `timestamp`
- `level`
- `event_type`
- `component`
- `message`
- `imei`
- `client_ip`
- `client_port`
- `details`

## Avvio manuale

Con virtualenv attivo:

```powershell
python main.py
```

Oppure con interpreter esplicito:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Avvio con PM2

Il progetto include una configurazione PM2 pronta:

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd start ecosystem.config.js
```

Per la gestione completa del processo, consulta:

- [PM2_GUIDE.md](PM2_GUIDE.md)

## Requisiti principali

- Python 3
- PostgreSQL
- virtualenv `.venv`
- dipendenze Python installate nel virtualenv
- PM2 per l'esecuzione persistente

## Note operative

- il parser supportato e' `Codec 8 TCP`
- il server valida il frame prima di inviare l'ACK
- il database mantiene lo stato corrente del tracker, non uno storico completo dei record
- i log applicativi stanno in `logs/`
- i log tecnici di PM2 stanno in `pm2-logs/`
- il server e' pensato per restare attivo h24
- per l'avvio automatico dopo reboot su Windows, consulta `PM2_GUIDE.md`
