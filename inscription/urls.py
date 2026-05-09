from django.urls import path

from . import views

app_name = "inscription"

urlpatterns = [
    path("", views.home, name="home"),
    path("inscription/", views.formulaire_inscription, name="formulaire"),
    path("confirmation/<int:candidat_id>/", views.confirmation, name="confirmation"),
    path("confirmation/<int:candidat_id>/pdf/", views.confirmation_pdf, name="confirmation_pdf"),
    path("quiz/", views.quiz_info, name="quiz"),
]
