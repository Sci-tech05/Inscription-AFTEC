# AFTEC 2026 - Plateforme d'inscription Django

Application Django de gestion des candidatures AFTEC 2026 (KcoMat, Pobè, Bénin) avec formulaire multi-étapes, quiz, upload de documents, PDF de confirmation candidat et administration avancée.

## Stack
- Django 4.2+
- SQLite
- Bootstrap 5 + JavaScript vanilla + AOS.js + Chart.js
- django-crispy-forms + crispy-bootstrap5
- ReportLab (génération PDF)
- python-decouple (variables d'environnement)

## Installation rapide
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata quiz_questions
python manage.py createsuperuser
python manage.py runserver
```

## Configuration `.env`
Un fichier `.env` est attendu à la racine du projet (même niveau que `manage.py`).

Variables importantes :
```env
SECRET_KEY=django-insecure-change-me-in-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,testserver

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=kcomat0@gmail.com
EMAIL_HOST_PASSWORD=
EMAIL_TIMEOUT=20
DEFAULT_FROM_EMAIL=KcoMat <kcomat0@gmail.com>
```

Notes Gmail (si utilisé) :
- Activez la validation en 2 étapes.
- Utilisez un mot de passe d'application Gmail dans `EMAIL_HOST_PASSWORD`.

## Fonctionnalités principales
- Landing page AFTEC 2026.
- Formulaire d'inscription en 6 étapes avec validations métier.
- Quiz de 30 questions avec scoring automatique.
- Confirmation de dossier avec numéro unique.
- Téléchargement PDF du **formulaire d'inscription** après validation (**sans section quiz**).
- Interface admin personnalisée (statistiques, filtres, actions, export CSV).
- Envoi d'emails administratifs de décision selon le statut candidat.

## URLs principales
- `/` : page d'accueil
- `/inscription/` : formulaire multi-étapes
- `/confirmation/<id>/` : confirmation candidature
- `/confirmation/<id>/pdf/` : formulaire PDF candidat
- `/quiz/` : aperçu quiz
- `/admin/` : administration AFTEC

## Arborescence
- `aftec2026/` : configuration du projet
- `inscription/` : app principale (models, views, forms, admin, templates)
- `inscription/fixtures/quiz_questions.json` : banque de questions
- `static/` : CSS/JS/images
- `media/` : documents candidats
- `templates/admin/custom_index.html` : dashboard admin personnalisé
