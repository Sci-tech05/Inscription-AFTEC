from django.urls import path

from . import views

app_name = "inscription"

urlpatterns = [
    path("", views.home, name="home"),
    path("inscription/", views.formulaire_inscription, name="formulaire"),
    path("confirmation/<int:candidat_id>/", views.confirmation, name="confirmation"),
    path("confirmation/<int:candidat_id>/pdf/", views.confirmation_pdf, name="confirmation_pdf"),
    path("quiz/", views.quiz_info, name="quiz"),
    path("challenges/", views.challenges_portal, name="challenges_portal"),
    path("challenges/login/", views.challenges_login, name="challenges_login"),
    path("challenges/logout/", views.challenges_logout, name="challenges_logout"),
    path("challenges/<int:challenge_id>/start/", views.challenge_start, name="challenge_start"),
    path("challenges/<int:challenge_id>/solve/", views.challenge_solve, name="challenge_solve"),
]
