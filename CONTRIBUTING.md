# CONTRIBUTING.md

## Welcome to Project Lyrica

Thank you for considering contributing to Project Lyrica! This guide will help you get started quickly and contribute effectively.

---

## Requirements

- Python 3.10 or higher
- A GitHub account

---

## Getting Started

### Fork & Clone the Repository

1. Go to the Project Lyrica GitHub page (https://github.com/VanilleIce/ProjectLyrica) and click "Fork" in the top right.
2. Clone your fork locally:

git clone https://github.com/YOUR_USERNAME/ProjectLyrica.git
cd ProjectLyrica

### Install Dependencies

pip install -r requirements.txt

---

## Testing

Tests are mandatory before any pull request is submitted.

Please verify the following manually:

python code/ProjectLyrica.py

Make sure:

- All features work as expected
- No new errors are introduced
- Translations follow the required structure
- The application starts without crashes

---

## Submitting Contributions

1. Create a feature branch:

git checkout -b feature/my-feature

2. Make your changes locally
3. Ensure they work and are tested
4. Use clear and descriptive commit messages, such as:

feat: added new French language file
fix: corrected XML error in de_DE.xml
docs: updated README with new screenshots

5. Push to your fork:

git push origin feature/my-feature

6. Submit a pull request via GitHub

Note: Both main and dev branches are protected. Contributions require CLA agreement (see below) and manual review by maintainers.

---

## Contributor License Agreement (CLA)

By submitting a pull request, you agree to the following terms:

1. Copyright License

You grant VanilleIce a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to:

- Use, reproduce, modify, and distribute your contribution
- Sublicense your contribution under the Project Lyrica license
- Include your contribution in commercial or non-commercial versions of Project Lyrica

2. Ownership

You retain copyright ownership of your contribution. This CLA does not transfer ownership — it grants the Author a license to use it.

3. Representations

You confirm that:

- You have the legal right to grant this license
- Your contribution does not infringe any third-party rights
- Your contribution is your original work, or you have permission to submit it

4. No Compensation

Contributions are voluntary and unpaid. You receive no compensation for your contribution.

5. Project License

Your contribution will be licensed under the Project Lyrica proprietary license (see LICENSE.md). You agree that the Author may change the license in the future.

---

## Adding Translations

1. Create a new file in resources/lang/, e.g. fr_FR.xml
2. Use this structure:

<?xml version="1.0" encoding="UTF-8"?>
<translations>
  <translation key="project_title">Projet Lyrica</translation>
  <translation key="file_select_title">Sélectionner une chanson</translation>
</translations>

3. Register the language in code/language_manager.py:

LANGUAGES = {
    "fr_FR": {"name": "Français", "layout": "AZERTY"},
}

4. Test the translation by selecting the language in the app

---

## Bug Reports & Feature Requests

### Reporting Bugs

- Clearly describe the issue
- Include reproduction steps
- Mention your environment:
  - Operating system (Windows 10/11, Linux, etc.)
  - Python version
  - Application version (see title bar or project_lyrica.log)
  - Screenshots, if applicable

### Requesting Features

- Open an issue to discuss your idea first
- Describe:
  - The benefit
  - Possible implementation
  - Impact on existing features

---

## Code Style

- Follow PEP 8
- Use type hints where possible
- Write docstrings for public functions
- Keep functions small and focused
- Use logging instead of print (except for CLI tools)

---

## What We Don't Accept

- Code copied from other projects without permission
- Changes that break existing functionality
- Contributions that violate the proprietary license
- Large refactorings without prior discussion

---

## Acknowledgments

Every contribution matters — whether it's a bugfix, a translation, or a suggestion.

Thank you for helping improve Project Lyrica.