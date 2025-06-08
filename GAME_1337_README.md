# 🎮 1337 Game - Cron-based Scheduling

## Überblick

Das **1337 Game** ist ein Discord-Spiel mit **flexiblem Scheduling** basierend auf Cron-Expressions. Spieler können Wetten platzieren und versuchen, so nah wie möglich an eine geheime Gewinnzeit heranzukommen, ohne sie zu überschreiten.

## ⚖️ Spielregeln

### Grundprinzip
- Spiele laufen zu **konfigurierbaren Zeiten** (Standard: täglich um 13:37:00)
- Der Bot generiert eine zufällige **Gewinnzeit** zwischen 0 und 60 Sekunden nach Spielstart
- Der Spieler, der **als letzter vor oder genau zur Gewinnzeit** eine Wette platziert, gewinnt

### Wettenarten

#### 🎯 **Normal-Wette (`/1337`)**
- Platziert eine Wette **zum Zeitpunkt der Eingabe**
- Nur während aktiver Spiele möglich
- Sofortiges Timing erforderlich

#### 🐦 **Early-Bird Wette (`/1337-early-bird <zeit>`)**
- Vorab definierte Zeit eingeben
- Format: `[hh:mm:]ss[.SSS]`
- Möglich während der **Early-Bird Periode** (Standard: 2 Stunden vor Spielstart)
- **Nur gültig**, wenn keine normale Wette innerhalb ±3 Sekunden der Gewinnzeit liegt

### Einschränkungen
- **Eine Wette pro Spiel** pro Benutzer
- Early-Bird nur während der Early-Bird Periode
- Normal-Wetten nur während aktiver Spiele

## 🔧 Konfiguration

### Umgebungsvariablen

```bash
# Cron Expression für Spielzeiten (Format: "minute hour day month dayofweek")
GAME_1337_CRON=37 13 * * *

# Early Bird Periode (Stunden vor Spielstart)
GAME_1337_EARLY_BIRD_CUTOFF_HOURS=2

# Zeitzone für Spiel-Scheduling
GAME_1337_TIMEZONE=Europe/Berlin

# Optional: Rollen-IDs für Belohnungen
GAME_1337_WINNER_ROLE_ID=123456789012345678
GAME_1337_EARLY_BIRD_ROLE_ID=123456789012345679
```

### Cron Expression Beispiele

| Beschreibung | Cron Expression | Erklärung |
|--------------|----------------|-----------|
| Täglich um 13:37 | `37 13 * * *` | Standard (Default) |
| Zweimal täglich (13:37 und 21:37) | `37 13,21 * * *` | Mittagspause und Abends |
| Nur Werktage um 13:37 | `37 13 * * 1-5` | Montag bis Freitag |
| Jede Stunde um :37 | `37 * * * *` | Stündliche Spiele |
| Alle 30 Minuten | `*/30 * * * *` | Häufige Spiele |
| Nur Wochenende um 15:00 | `0 15 * * 6,0` | Samstag und Sonntag |

### Debug-Scheduling

Für Tests und Debugging können Sie häufigere Spiele einstellen:

```bash
# Alle 5 Minuten (zu Testzwecken)
GAME_1337_CRON=0 */5 * * * *

# Alle Minute (nur für Entwicklung!)
GAME_1337_CRON=0 * * * * *
```

**⚠️ Warnung:** Sehr häufige Spiele (jede Minute) sollten nur zur Entwicklung verwendet werden!

## 🕐 Zeitformat Beispiele

| Eingabe         | Bedeutung                    | Millisekunden |
|-----------------|------------------------------|---------------|
| `13.5`          | 13,5 Sekunden               | 13500         |
| `01:13`         | 1 Minute 13 Sekunden        | 73000         |
| `1:02:03.999`   | 1h 2min 3,999s              | 3723999       |
| `60.000`        | 60 Sekunden (Maximum)        | 60000         |

### ⚠️ Wichtige Regeln
- **Punkt** (.) für Dezimalstellen verwenden, **nicht Komma**
- Maximum: **60.000 Sekunden**
- Gültige Zeichen: Zahlen, Doppelpunkt (:), Punkt (.)

## 🎮 Commands

### `/1337`
Platziert eine **Echtzeit-Wette** zum Moment der Eingabe.

**Beispiel:**
```
/1337
```
→ Wette wird sofort zum aktuellen Zeitpunkt platziert (nur während aktiver Spiele)

### `/1337-early-bird <zeit>`
Platziert eine **Early-Bird Wette** mit vordefinierter Zeit.

**Beispiele:**
```
/1337-early-bird 30.5
/1337-early-bird 01:15
/1337-early-bird 45.123
```

### `/1337-next`
Zeigt die **nächsten geplanten Spiele** und aktuellen Status an.

**Features:**
- Aktueller Status (aktives Spiel, Early-Bird Periode, oder wartend)
- Nächste 5 geplante Spiele
- Cron-Expression und Zeitzone-Info

### `/1337-info`
Zeigt Informationen über deine aktuelle Wette an.

**Features:**
- Deine Wette für aktuelles/nächstes Spiel
- Spielstatus und Zeitinformationen
- Ergebnisse nach Spielende

### `/1337-stats`
Zeigt die Statistiken und Bestenlisten an.

**Features:**
- Aktuelles/letztes Spiel
- Alle Spieler und ihre Wetten
- Gewinner-Information (nach Spielende)

## 🏆 Belohnungssystem (Optional)

### Rollen (falls konfiguriert)

| Rolle                 | Bedingung           |
|-----------------------|---------------------|
| **Winner Role**       | Gewinner eines Spiels |
| **Early Bird Role**   | Early-Bird Wetten   |

### Rang-System (Drei-Stufen-System)

Basierend auf der Gesamtzahl der Siege erhalten Spieler automatisch Rangabzeichen:

| Rang             | Bedingung    | Umgebungsvariable |
|------------------|--------------|-------------------|
| **🎖️ Leet Sergeant** | 1+ Siege     | `GAME_1337_LEET_SERGEANT_ROLE_ID` |
| **⭐ Leet Commander** | 5+ Siege     | `GAME_1337_LEET_COMMANDER_ROLE_ID` |
| **👑 Leet General**   | 10+ Siege    | `GAME_1337_LEET_GENERAL_ROLE_ID` |

**Features:**
- Automatische Rollenverwaltung nach jedem Spiel
- Hierarchisches System (höhere Ränge ersetzen niedrigere)
- Vollständige Spielerstatistiken-Verfolgung
- Integration mit Discord-Rollensystem

## 🎯 Gewinnlogik

### Normal-Wetten
- Alle normalen Wetten sind immer gültig
- Der späteste Spieler ≤ Gewinnzeit gewinnt

### Early-Bird Wetten
- **Nur gültig** wenn **keine normale Wette** innerhalb ±3 Sekunden der Gewinnzeit liegt
- Ansonsten werden Early-Bird Wetten ignoriert

### Beispiel-Szenario
```
Gewinnzeit: 45.000s

Normale Wetten:
- Spieler A: 42.500s ✅
- Spieler B: 44.800s ✅ (Gewinner - späteste gültige Wette)
- Spieler C: 45.200s ❌ (zu spät)

Early-Bird Wette:
- Spieler D: 44.900s ❌ (normale Wette innerhalb ±3s vorhanden)
```

## ⚙️ Technische Details

### Scheduler-System
- **Cron-basiert:** Flexibles Scheduling mit croniter
- **Asynchron:** Non-blocking Scheduler-Loop
- **Persistent:** Läuft dauerhaft im Hintergrund
- **Zeitzone-aware:** Konfigurierbare Zeitzone

### Spiellogik
- **Deterministische Zufallszahlen:** Gleiche Gewinnzeit für gleichen Spieltermin
- **Datenbankbasiert:** Alle Wetten werden persistent gespeichert
- **Multi-Guild Support:** Jede Guild kann separate Spiele haben

### Datenstruktur
```sql
CREATE TABLE game_1337_bets (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(20) NOT NULL,
    username VARCHAR(100) NOT NULL,
    play_time INTEGER NOT NULL,           -- Millisekunden nach Spielstart
    play_type ENUM('normal', 'early') NOT NULL,
    date VARCHAR(10) NOT NULL,            -- YYYY-MM-DD
    guild_id VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🚀 Setup für Admins

### 1. Konfiguration
```env
# .env Datei
GAME_1337_CRON=37 13 * * *              # Täglich um 13:37
GAME_1337_EARLY_BIRD_CUTOFF_HOURS=2       # 2h Early-Bird Periode
GAME_1337_TIMEZONE=Europe/Berlin          # Zeitzone
```

### 2. Docker Installation
```bash
# Mit croniter dependency
docker build -t vibebot .
docker run -d --name vibebot --env-file .env vibebot
```

### 3. Bot-Berechtigungen
- Slash Commands verwenden
- Nachrichten senden
- Rollen verwalten (optional)

## 📊 Überwachung und Debugging

### Logs überprüfen
```bash
# Scheduler-Logs
tail -f logs/game_1337.log

# Command-Logs  
tail -f logs/commands_1337_cron.log
```

### Status überprüfen
- `/1337-next` - Zeigt nächste Spiele und aktuellen Status
- Logs zeigen Scheduler-Aktivität und Fehler

### Häufige Probleme
1. **Keine Spiele:** Cron-Expression überprüfen
2. **Falsche Zeiten:** Zeitzone-Konfiguration überprüfen
3. **Scheduler stoppt:** Bot-Restart erforderlich

## 🎪 Tipps für Spieler

1. **Zeitplan kennen:** `/1337-next` zeigt alle kommenden Spiele
2. **Early-Bird nutzen:** Für konsistente Strategien
3. **Status prüfen:** `/1337-info` zeigt deinen aktuellen Stand
4. **Flexibilität:** Spiele können zu verschiedenen Zeiten stattfinden

## 🔄 Migration von festen Zeiten

Falls Sie von einem festen Zeitplan (13:37 täglich) zu Cron-Scheduling wechseln:

1. Backup der Datenbank erstellen
2. Neue Umgebungsvariablen setzen
3. Bot mit cron-commands neu starten
4. Testen mit `/1337-next`

---

**Viel Erfolg beim 1337 Game mit flexiblem Scheduling!** 🍀

*Das Cron-basierte System ermöglicht maximale Flexibilität für Community-Events und angepasste Spielzeiten.*
