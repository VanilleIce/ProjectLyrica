# 🎹 Project Lyrica

[![CLA assistant](https://cla-assistant.io/readme/badge/VanilleIce/ProjectLyrica)](https://cla-assistant.io/VanilleIce/ProjectLyrica)

**Automatischer Musik-Player für _Sky: Children of the Light_**  
Spiele deine Lieblingssongs mit perfektem Timing stilvoll ab.

---

## ✨ Was macht Project Lyrica?

**Project Lyrica** verwandelt Songsheets im JSON-Format in präzise Tasteneingaben, um Musik automatisch in **Sky: Children of the Light** abzuspielen.  
Einfach Song auswählen, auf „Play“ klicken – und genießen!

---

## 🔑 Hauptfunktionen

- 🎼 **Plug & Play** – Lade beliebige Songdateien und spiele sie sofort ab  
- 🎚️ **Präzise Steuerung**  
  - Wiedergabegeschwindigkeit: 600–1200 BPM  
  - Notenlänge einstellbar: 0.1–1.0 Sekunden  
- ⏯️ **Intelligente Wiedergabe**  
  - Pause/Fortsetzen während der Wiedergabe mit `#`  
  - Automatischer Fokus auf das Spiel  
- 🌐 **Mehrsprachigkeit** – Englisch, Deutsch & mehr (via XML)  
- 🎛️ **Benutzerdefinierte Tastenzuweisung**  
- 💾 **Presets** – Lieblingskonfigurationen speichern & laden  

---

## 🛠️ Installation

**Voraussetzungen:**

```bash
pip install pygetwindow customtkinter pynput
```

**Projekt herunterladen:**

```bash
git clone https://github.com/VanilleIce/ProjectLyrica.git
cd ProjectLyrica
```

**Anwendung starten:**

```bash
python _ProjectLyrica.py
```

> ✅ **Systemanforderungen:** Windows 10/11 • Python 3.10+ • Sky: Children of the Light

---

## 🎮 Anwendung

1. Songdateien nach `/resources/Songs/` verschieben (`.json`, `.txt`, `.skysheet` werden unterstützt)  
2. Anwendung starten  
3. Song im Dateibrowser auswählen  
4. Optional:  
   - Notendauer aktivieren  
   - Geschwindigkeit einstellen (1000 = Originaltempo)  
5. Stelle sicher, dass _Sky_ läuft 
6. Klicke auf **Play** und genieße das Konzert  
7. Mit `#` jederzeit pausieren oder fortsetzen

![Lyrica v2.0 Interface](https://via.placeholder.com/500x450?text=Lyrica+v2.0+Interface)

---

## 🚀 Neu in Version 2.0

```diff
+ SMOOTH SPEED RAMPING - Natürlichere Temposprünge
+ DYNAMIC UI - Automatisch skalierende Benutzeroberfläche
+ THREAD-SAFE OPERATIONS - Stabilere Wiedergabe ohne Abstürze
+ IMPROVED TRANSLATIONS - Schnellere Sprachumschaltung
+ OPTIMIZED FOCUS - Zuverlässiger Spiel-Fokus
+ PRESET SYSTEM - Einstellungen speichern & laden
```

---

## 🤝 Mitwirken

Wir freuen uns über Beiträge! Bitte beachte:

- Unterzeichne das CLA  
- Beachte die Lizenz (AGPLv3)  
- Melde Fehler via GitHub-Issues  
- Reiche Pull Requests ein

---

## ⚠️ Fehlerbehebung

- **Spiel wird nicht erkannt?**  
  läuft Sky überhaupt?

- **Tasten werden nicht gedrückt?**  
  Prüfe die Tastenzuweisung in `settings.json`  

- **Sprachprobleme?**  
  Überprüfe die XML-Dateien im Ordner `/resources/lang/`  

---

> 🌈 _„Project Lyrica schlägt eine Brücke zwischen Komponisten und Spielern und macht Musik in Sky für alle zugänglich.“_