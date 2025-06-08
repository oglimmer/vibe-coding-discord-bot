# 🐳 Docker Deployment für VibeBot

## Schnellstart

1. **Umgebungsvariablen setzen:**
   ```bash
   cp .env.example .env
   # Bearbeite .env und setze deinen BOT_TOKEN
   ```

2. **Bot starten:**
   ```bash
   docker compose up -d
   ```

3. **Logs ansehen:**
   ```bash
   docker compose logs -f vibebot
   ```

## Services

### 🤖 VibeBot (Discord Bot)
- **Container:** `vibebot-discord`
- **Port:** Keiner (Discord Bot)
- **Logs:** `./logs/` (Volume gemountet)

### 🐘 PostgreSQL Datenbank
- **Container:** `vibebot-postgres`
- **Port:** `5432` (extern verfügbar)
- **Data:** `postgres_data` Volume
- **Init:** Automatisch mit `postgresql_init.sql`

### 🌐 pgAdmin (Optional)
- **Container:** `vibebot-pgadmin`
- **Port:** `8080` (nur mit `--profile admin`)
- **Login:** `admin@vibebot.local` / Dein DB_PASSWORD

## Kommandos

### Alle Services starten
```bash
docker compose up -d
```

### Mit pgAdmin starten
```bash
docker compose --profile admin up -d
```

### Bot neu starten
```bash
docker compose restart vibebot
```

### Logs ansehen
```bash
# Alle Services
docker compose logs -f

# Nur Bot
docker compose logs -f vibebot

# Nur Datenbank
docker compose logs -f postgres
```

### Services stoppen
```bash
docker compose down
```

### Alles löschen (inkl. Datenbank!)
```bash
docker compose down -v
```

## Konfiguration

### Umgebungsvariablen (.env)
```env
# Bot Token (PFLICHT)
BOT_TOKEN=dein_discord_bot_token_hier

# Zeitzone
TZ=Europe/Berlin

# Datenbank
DB_NAME=meine_datenbank
DB_USER=admin
DB_PASSWORD=geheim
```

### Datenbank-Zugang von außen
Die PostgreSQL-Datenbank ist über Port `5432` erreichbar:
```bash
psql -h localhost -p 5432 -U admin -d meine_datenbank
```

### pgAdmin Web-Interface
Wenn mit `--profile admin` gestartet:
- URL: http://localhost:8080
- Email: admin@vibebot.local
- Password: Dein DB_PASSWORD

## Entwicklung

### Bot-Code ändern
1. Code bearbeiten
2. Container neu bauen: `docker compose build vibebot`
3. Neu starten: `docker compose up -d vibebot`

### Datenbank zurücksetzen
```bash
docker compose down postgres
docker volume rm discord-bot_postgres_data
docker compose up -d postgres
```

## Troubleshooting

### Bot startet nicht
```bash
# Logs prüfen
docker compose logs vibebot

# Container-Status prüfen
docker compose ps
```

### Datenbank-Verbindungsfehler
```bash
# Datenbank-Status prüfen
docker compose logs postgres

# Verbindung testen
docker compose exec postgres pg_isready -U admin
```

### Berechtigungen
```bash
# Logs-Ordner Berechtigung
sudo chown -R $USER:$USER ./logs/
```

## Monitoring

### Gesundheitschecks
```bash
docker compose ps
```

### Ressourcenverbrauch
```bash
docker stats vibebot-discord vibebot-postgres
```

## Backup

### Datenbank-Backup
```bash
docker compose exec postgres pg_dump -U admin meine_datenbank > backup.sql
```

### Datenbank-Restore
```bash
docker compose exec -T postgres psql -U admin meine_datenbank < backup.sql
```
