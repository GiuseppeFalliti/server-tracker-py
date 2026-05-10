# Guida systemd

Questo progetto, sulla macchina target, usa `systemd` per gestire i servizi backend.

## Servizi da gestire

I servizi applicativi tipici sono:

- `tracker-dashboard-api`
- `tracker-tcp-server`

Il nome esatto puo' variare in base alla configurazione della VM. Se hai dubbi, controlla l'elenco dei servizi:

```bash
systemctl list-units --type=service | grep -i tracker
```

## Comandi principali

### Verifica stato servizio API

```bash
sudo systemctl status tracker-dashboard-api
```

### Riavvio servizio API

```bash
sudo systemctl restart tracker-dashboard-api
```

### Verifica stato server TCP

```bash
sudo systemctl status tracker-tcp-server
```

### Riavvio server TCP

```bash
sudo systemctl restart tracker-tcp-server
```

### Avvio servizio

```bash
sudo systemctl start tracker-dashboard-api
```

### Stop servizio

```bash
sudo systemctl stop tracker-dashboard-api
```

### Abilitazione all'avvio automatico

```bash
sudo systemctl enable tracker-dashboard-api
```

### Disabilitazione avvio automatico

```bash
sudo systemctl disable tracker-dashboard-api
```

## Log dei servizi

Per vedere gli ultimi log del servizio API:

```bash
journalctl -u tracker-dashboard-api -n 100 --no-pager
```

Per seguire i log live:

```bash
journalctl -u tracker-dashboard-api -f
```

Per il server TCP:

```bash
journalctl -u tracker-tcp-server -n 100 --no-pager
```

## Flusso consigliato dopo modifiche backend

Da `backend/`:

```bash
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart tracker-dashboard-api
```

Se hai modificato anche il server TCP:

```bash
sudo systemctl restart tracker-tcp-server
```

## Flusso consigliato dopo modifiche frontend

Da `frontend/`:

```bash
npm install
npm run build
```

Se il frontend e' servito da un web server o da un altro servizio, riavvia anche quello secondo la configurazione della VM.

## Diagnostica rapida

### Controllare se il servizio esiste

```bash
systemctl list-unit-files | grep -i tracker
```

### Verificare se il servizio e' attivo

```bash
systemctl is-active tracker-dashboard-api
```

### Verificare se il servizio parte al boot

```bash
systemctl is-enabled tracker-dashboard-api
```

## Note operative

- dopo modifiche Python non basta aggiornare i file: serve il riavvio del servizio
- dopo nuove dipendenze Python va rieseguito `pip install -r requirements.txt`
- dopo modifiche React va ricostruita la build frontend
- se `marca`, `model` o `citta` non cambiano in dashboard, controlla prima che il servizio API sia stato davvero riavviato
