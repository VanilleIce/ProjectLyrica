# 🎹 Project Lyrica

[![CLA assistant](https://cla-assistant.io/readme/badge/VanilleIce/ProjectLyrica)](https://cla-assistant.io/VanilleIce/ProjectLyrica)

**Automatic Music Player for _Sky: Children of the Light_**  
Stylishly play your favorite songs with perfect timing.

---

## ✨ What Does Project Lyrica Do?

**Project Lyrica** transforms JSON-format song sheets into precise keystrokes to automatically perform music in **Sky: Children of the Light**.  
Simply select a song, click “Play” – and enjoy!

---

## 🔑 Key Features

- 🎼 **Plug & Play** – Load any compatible song and play instantly  
- 🎚️ **Precision Controls**  
  - Playback speed: 600–1200 BPM  
  - Custom note duration: 0.1–1.0 seconds  
- ⏯️ **Smart Playback**  
  - Pause/resume mid-performance with `#`  
  - Automatic focus on the game window  
- 🌐 **Multi-language Support** – English, German & more via XML  
- 🎛️ **Custom Key Bindings**  
- 💾 **Presets** – Save and load favorite configurations  

---

## 🛠️ Installation

**Requirements:**

```bash
pip install pygetwindow customtkinter pynput
```

**Download Project:**

```bash
git clone https://github.com/VanilleIce/ProjectLyrica.git
cd ProjectLyrica
```

**Launch Application:**

```bash
python ProjectLyrica.py
```

> ✅ **System Requirements:** Windows 10/11 • Python 3.10+ • Sky: Children of the Light

---

## 🎮 How to Use

1. Move your song files to `/resources/Songs/` (supports `.json`, `.txt`, `.skysheet`)  
2. Launch the app  
3. Select a song using the file browser  
4. Optional:  
   - Enable note duration  
   - Set playback speed (1000 = original tempo)  
5. Make sure _Sky_ is running  
6. Click **Play** and enjoy the performance  
7. Press `#` anytime to pause or resume

---

## Tastenbelegung anpassen

1. open the file `settings.json` in a text editor
2. search for the section `‘key_mapping’`.
3. change the values as required:
   ```json
   "key_mapping": {
       "Key0": "your key",
       "Key1": "your key",
       ...
   }

---

## 🚀 What’s New in Version 2.0

```diff
+ SMOOTH SPEED RAMPING - More natural tempo changes
+ DYNAMIC UI - Auto-scaling interface
+ THREAD-SAFE OPERATIONS - Crash-resistant playback
+ IMPROVED TRANSLATIONS - Faster language switching
+ OPTIMIZED FOCUS - Reliable window targeting
+ PRESET SYSTEM - Save/load your favorite settings
```

---

## 🤝 Contributing

We welcome your contributions! Please:

- Sign the CLA  
- Follow the AGPLv3 license terms  
- Report bugs via GitHub Issues  
- Submit pull requests to the dev branch

---

## ⚠️ Troubleshooting

- **Sky window not detected?**  
  Is the game actually running?

- **Keys not pressing?**  
  Check key bindings in `settings.json`  

- **Translation issues?**  
  Inspect the XML files in `/resources/lang/`  

---

> 🌈 _“Project Lyrica bridges the gap between composers and performers, making music in Sky accessible to everyone.”_
