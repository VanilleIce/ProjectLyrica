# CONTRIBUTING.md

## 💖 Welcome to **Project Lyrica**

Thank you for considering contributing to **Project Lyrica**! This guide will help you get started quickly and contribute effectively.

---

## 📋 Requirements

- Python **3.10** or higher
- A GitHub account

---

## 🚀 Getting Started

### 🔀 Fork & Download the Repository

1. Go to the [Project Lyrica GitHub page](https://github.com/VanilleIce/ProjectLyrica) and click **"Fork"** in the top right.
2. Download the repository as a `.zip` file and extract it locally.

### 📦 Install Dependencies

> A `requirements.txt` file will be provided – install it before working on the project:

```bash
pip install -r requirements.txt
```

---

## 🧪 Testing

**Tests are mandatory before any pull request is submitted.**

Please verify the following manually:

```bash
python ProjectLyrica.py
```

Make sure:

- All features work as expected
- No new errors are introduced
- Translations follow the required structure

---

## 🔧 Submitting Contributions

1. Make your changes locally
2. Ensure they work and are tested
3. Use clear and descriptive commit messages, such as:

```text
feat: added new French language file
fix: corrected XML error in *.xml
```

4. Submit a pull request via GitHub

> ⚠️ Note: Both `main` and `dev` branches are protected. Contributions require CLA agreement and possibly manual review by maintainers.

---

## 🌍 Adding Translations

1. Create a new file in `resources/lang/`, e.g. `fr_FR.xml`
2. Use this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<translations>
  <translation key="example_key">Translation</translation>
</translations>
```

3. Register the language in `resources/config/lang.xml`:

```xml
<language code="fr_FR" key_layout="AZERTY">Français</language>
```

---

## 🐛 Bug Reports & Feature Requests

### Reporting Bugs

- Clearly describe the issue
- Include reproduction steps
- Mention your environment:
  - Operating system
  - Python version
  - Screenshots, if applicable

> ⚠️ There are currently **no issue templates** – clarity is appreciated!

### Requesting Features

- Open an issue to discuss your idea first
- Describe:
  - The benefit
  - Possible implementation
  - Impact on existing features

---

## ⚖️ License

By contributing, you agree that your changes will be licensed under the **AGPLv3** license.

---

## 🙏 Acknowledgments

Every contribution matters – whether it’s a bugfix, a translation, or a suggestion.  
**Thank you for helping improve Project Lyrica.**
