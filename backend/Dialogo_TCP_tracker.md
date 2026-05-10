# Esempio di dialogo TCP tracker -> server

Questo file mostra una sessione realistica tra un tracker Teltonika e il server TCP del progetto.

## 1. Connessione iniziale

Il tracker apre una connessione TCP verso:

```text
SERVER_IP:5001
```

## 2. Handshake IMEI

Nel protocollo Teltonika, il tracker invia:

```text
[2 byte lunghezza IMEI][IMEI ASCII]
```

Esempio:

```text
000F333532303933303831343239313530
```

Significato:

- `000F` = lunghezza IMEI `15`
- `333532303933303831343239313530` = ASCII di `352093081429150`

## 3. Risposta del server

Se l'IMEI viene accettato, il server risponde:

```text
01
```

Se il dispositivo venisse rifiutato, la risposta logica sarebbe:

```text
00
```

## 4. Invio del frame AVL

Dopo l'handshake, il tracker invia un frame AVL TCP:

```text
[preamble][data field length][codec id][number of data 1][AVL data ...][number of data 2][CRC]
```

Esempio reale abbreviato:

```text
00000000000004d2081d00000176ccb78948...
```

Campi principali:

- `00000000` = preamble
- `000004d2` = lunghezza dati
- `08` = `Codec 8`
- `1d` = `29` record AVL dichiarati
- `...` = payload AVL
- `1d` finale = conferma del numero record
- `000027ca` = CRC finale

## 5. Cosa fa il server

Quando riceve il frame AVL, il server:

1. verifica il `preamble`
2. verifica il `codec id`
3. confronta `number of data 1` e `number of data 2`
4. valida il `CRC-16/IBM`
5. decodifica i record AVL
6. estrae il `primary_record`
7. salva i dati su PostgreSQL
8. invia l'ACK finale

## 6. ACK finale

Il server risponde con il numero di record accettati in 4 byte big-endian.

Se i record accettati sono `29`, l'ACK e':

```text
0000001d
```

## 7. Sequenza compatta

```text
TRACKER -> SERVER
000F333532303933303831343239313530

SERVER -> TRACKER
01

TRACKER -> SERVER
00000000000004d2081d00000176ccb78948...

SERVER -> TRACKER
0000001d
```

## 8. Struttura logica del record decodificato

Dal payload AVL il backend costruisce un dizionario nel formato usato dal resto del progetto:

```python
{
    "imei": "352093081429150",
    "codecid": 8,
    "no_record_i": 29,
    "no_record_e": 29,
    "d_time_unix": 1609621190808,
    "d_time_local": "2021-01-03 02:29:50",
    "lon": 801065150,
    "lat": 130466366,
    "speed": 0,
    "io_data": {...}
}
```

## 9. Risultato applicativo

Dopo la persistenza:

- `tracker` contiene lo stato del veicolo
- `tracker_data` contiene l'ultima telemetria
- `api/vehicles` espone i dati alla dashboard
- il frontend mostra posizione, popup, `citta`, `marca`, `model`, `km` e `speed`
