# Guida PM2 per il Server TCP

## Panoramica

PM2 e' il process manager usato per mantenere online il server TCP Python anche quando chiudi terminale, progetto o VS Code.

Nel progetto viene usato per:

- avviare `main.py` con il Python del virtualenv
- riavviare automaticamente il processo in caso di crash
- mantenere il listener TCP sempre attivo
- ripristinare il processo dopo login o reboot, in base alla configurazione disponibile su Windows

## Cosa supervisiona PM2

PM2 non gestisce la logica Teltonika: supervisiona il processo Python che la esegue.

In pratica il processo monitorato da PM2 fa:

- parsing binario dell'`IMEI handshake`
- parsing completo del frame `Codec 8 TCP`
- validazione di `preamble`, `record count` e `CRC-16/IBM`
- decodifica dei blocchi I/O `N1`, `N2`, `N4`, `N8`
- persistenza su PostgreSQL
- logging JSON strutturato

Se il tracker invia un frame malformato:

- PM2 non "corregge" il pacchetto
- il processo puo' restare online
- il frame viene rifiutato dal parser
- l'evento viene tracciato nei log JSON applicativi

## File coinvolti

- `ecosystem.config.js`: definisce il processo `tracker-tcp-server`
- `start-pm2-server.cmd`: esegue `pm2 resurrect` usando `PM2_HOME` del progetto
- `pm2-home/`: contiene dump PM2, pid e metadata runtime
- `pm2-logs/`: contiene i log tecnici del processo PM2

## Comandi principali

### Verifica stato

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd status
```

Mostra se `tracker-tcp-server` e' online, il PID, l'uptime e i restart.

### Avvio del server

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd start ecosystem.config.js
```

Avvia il processo definito in `ecosystem.config.js`.

### Riavvio del server

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd restart tracker-tcp-server
```

Riavvia il processo. Questo non modifica il comportamento del parser: riavvia semplicemente il listener TCP e il decoder gia' integrato nel progetto.

### Stop del server

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd stop tracker-tcp-server
```

Ferma il server mantenendo comunque la configurazione PM2.

### Eliminazione del processo da PM2

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd delete tracker-tcp-server
```

Rimuove il processo dalla lista di PM2. Usalo solo se vuoi eliminare completamente la definizione attiva.

## Log PM2

### Visualizzare i log del supervisore

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd logs tracker-tcp-server
```

Mostra i log di output ed errore del processo gestito da PM2.

### File di log PM2

Nel progetto i file PM2 sono:

- `pm2-logs/tracker-tcp-server-out.log`
- `pm2-logs/tracker-tcp-server-error.log`

Questi file servono soprattutto per capire:

- se il processo parte correttamente
- se crasha subito
- se PM2 lo ha riavviato
- se ci sono errori di bootstrap del runtime Python

Non sostituiscono i log applicativi JSON.

## Log da consultare per il protocollo

Per il debug operativo del protocollo Teltonika, i log principali sono:

- `logs/system.json`
- `logs/<IMEI>/YYYY-MM-DD.json`

Qui trovi informazioni su:

- connessioni TCP
- IMEI ricevuti
- frame AVL accettati o rifiutati
- errori di framing
- mismatch del `record count`
- `CRC` invalido
- persistenza su database
- ACK inviati al tracker

## Salvataggio della process list

Per salvare i processi correnti da ripristinare con `resurrect`:

```powershell
set PM2_HOME=c:\Users\Admin\Desktop\server_tracker\server_py\pm2-home
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd save --force
```

Questo aggiorna:

- `pm2-home/dump.pm2`

## Ripristino della process list

Per ripristinare i processi salvati:

```powershell
set PM2_HOME=c:\Users\Admin\Desktop\server_tracker\server_py\pm2-home
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd resurrect
```

Nel progetto questo comando e' gia' incapsulato in:

- `start-pm2-server.cmd`

## Comandi utili di diagnostica

### Elenco processi

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd ls
```

### Dettaglio di un processo

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd describe tracker-tcp-server
```

### Monitor in tempo reale

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd monit
```

### Versione PM2

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd -v
```

## Riavvio automatico su Windows

### Soluzione ideale

La soluzione piu' robusta e' installare PM2 come servizio Windows:

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2-service-install.cmd --unattended
```

Nota importante:

- il comando richiede un terminale eseguito come amministratore

### Fallback gia' predisposto nel progetto

Se non hai privilegi amministratore, il progetto usa un bootstrap utente che richiama:

- `start-pm2-server.cmd`

all'accesso dell'utente Windows.

Script predisposto:

- `C:\Users\Admin\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\tracker-tcp-server-startup.cmd`

In questo modo, al login dell'utente, PM2 esegue `resurrect` e riporta online il server.

## Flusso operativo consigliato

### Primo setup

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd start ecosystem.config.js
set PM2_HOME=c:\Users\Admin\Desktop\server_tracker\server_py\pm2-home
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd save --force
```

### Controllo giornaliero

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd status
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd logs tracker-tcp-server
```

### Dopo modifiche al codice

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd restart tracker-tcp-server
```

Se hai cambiato la configurazione PM2:

```powershell
C:\Users\Admin\AppData\Roaming\npm\pm2.cmd start ecosystem.config.js
```

## Differenza tra log PM2 e log applicativi

### Log PM2

Servono per capire:

- se il processo parte
- se crasha subito
- se PM2 lo ha riavviato
- eventuali errori di bootstrap del processo

### Log applicativi JSON

Servono per capire:

- cosa fa il server TCP
- come viene gestito l'`IMEI handshake`
- quali frame `Codec 8 TCP` arrivano
- se il `CRC-16/IBM` e' valido
- quanti record contiene il pacchetto
- cosa viene salvato nel database
- quali errori applicativi avvengono durante il flusso

Percorsi:

- `logs/system.json`
- `logs/<IMEI>/YYYY-MM-DD.json`
