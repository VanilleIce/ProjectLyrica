# 🎹 Project Lyrica 
 
[![CLA assistant](https://cla-assistant.io/readme/badge/VanilleIce/ProjectLyrica)](https://cla-assistant.io/VanilleIce/ProjectLyrica) 
 
## 📜 License 
 
Project Lyrica is licensed under the **AGPLv3 with commercial use restriction**. 
You may not use this software for any commercial purpose without explicit permission. 
 
[View Full License](LICENSE) | [Contributor Agreement](CLA.md) 
 
--- 
 
## ✨ What Does Project Lyrica Do? 
 
**Project Lyrica** converts songs in JSON/Skysheet format into precise keystrokes to automatically play music in **Sky: Children of the Light**.
Simply select a song, click “Play,” and enjoy! 
 
--- 
 
## 🔑 Key Features 
 
- 🎼 **Plug & Play** – Load any compatible song and play instantly 
- 🎚️ **Precision Controls** 
  - Playback speed: 600–1500 BPM  -> preferably up to 1200
  - Custom note duration: 0.1–1.0 seconds 
  - Smooth speed ramping for natural transitions 
- ⏯️ **Smart Playback** 
  - Pause/resume mid-performance with customizable hotkey 
  - Automatic focus on the game window 
  - Intelligent pause handling with resume ramping 
- 🌐 **Multi-language Support** – 15+ languages with automatic keyboard layouts 
- ⌨️ **Visual Key Editor** – Customize key bindings with intuitive interface 
- 💾 **Preset System** – Save and load favorite Presets
- 🎛️ **Comprehensive Settings** – Fine-tune timing, delays, and behavior
 
--- 
 
## 🛠️ Installation 

### 🎯 For End Users (Recommended)

 1. **Download the latest release from** [GitHub Releases](https://github.com/VanilleIce/ProjectLyrica/releases)
 2. **Run** ^`ProjectLyrica_setup.exe^` **and follow the installer**
 3. **Start the Lyrica project** from the folder.
 
### 🔧 For Developers

**Requirements:** 
 
```bash 
pip install -r requirements.txt 
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
 
1. **First Launch:** The app will guide you to locate your Sky.exe file 
2. **Add new Songs:** Place song files in /resources/Songs/ (supports .json, .txt, .skysheet) 
3. **Select Song:** Use the file browser to choose your music 
4. **Configure Playback:** 
   - Enable **Note Duration** for custom press lengths 
   - Set **Playback Speed** (1000 = original tempo) 
   - Toggle **Smooth Ramping** for natural speed transitions 
5. **Play Music:** 
   - Ensure _Sky: Children of the Light_ is running 
   - Click **Play** and enjoy the performance 
   - Use your pause key (default: #) to pause/resume anytime 
 
--- 
 
## ⚙️ Customization 
 
### Keyboard Layouts 
- Access **Settings** → **Edit Keys** for visual key mapping 
- Choose from 6+ regional layouts (QWERTY, AZERTY, QWERTZ, JIS, etc.) 
- Create and save custom layouts 
- Automatic layout selection based on language 
 
### Advanced Settings 
- **Timing Controls:** Fine-tune initial delays and pause/resume timing 
- **Ramping Configuration:** Customize speed transition curves 
- **UI Preferences:** Dark/Light theme, language selection 
- **Game Integration:** Sky.exe path management 
 
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
  Verify the game is running and the correct executable path is set in Settings 
 
- **Keys not pressing?** 
  Use the Key Editor to verify and customize your key bindings 
 
- **Playback issues?** 
  Adjust timing settings and enable/disable smooth ramping 
 
- **Translation issues?** 
  Check language settings and report missing translations 
 
--- 
 
## 🎵 Supported Formats 
 
- **JSON** (Standard Sky sheet format) 
- **TXT** (Legacy format) 
- **SkySheet** (Community format) 
 
--- 
 
🌈 *"Project Lyrica bridges the gap between composers and performers, making music in Sky accessible to everyone."* 