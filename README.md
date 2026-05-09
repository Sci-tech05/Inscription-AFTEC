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

