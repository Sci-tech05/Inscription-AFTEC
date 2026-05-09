from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def validate_file_size(file_obj):
    max_size = 5 * 1024 * 1024
    if file_obj.size > max_size:
        raise ValidationError("La taille du fichier ne doit pas dépasser 5 Mo.")


def validate_file_extension(file_obj):
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    name = file_obj.name.lower()
    if not any(name.endswith(ext) for ext in allowed_extensions):
        raise ValidationError("Format non autorisé. Utilisez PDF, JPG ou PNG.")


class Candidat(models.Model):
    SEXE_CHOICES = (
        ("M", "Masculin"),
        ("F", "Féminin"),
    )

    CLASSE_CHOICES = (
        ("4EME", "4ème"),
        ("3EME", "3ème"),
        ("2NDE", "2nde"),
        ("1ERE", "1ère"),
        ("TLE", "Terminale"),
        ("L1", "Licence 1"),
        ("L2", "Licence 2"),
        ("L3", "Licence 3"),
        ("M1", "Master 1"),
        ("M2", "Master 2"),
        ("AUTRE", "Professionnel"),
    )

    nom = models.CharField(max_length=120)
    prenom = models.CharField(max_length=120)
    date_naissance = models.DateField()
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    telephone = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    commune_residence = models.CharField(max_length=120)
    etablissement = models.CharField(max_length=255)
    classe_niveau = models.CharField(max_length=10, choices=CLASSE_CHOICES)
    filiere = models.CharField(max_length=120)
    numero_dossier = models.CharField(max_length=32, unique=True, blank=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date_inscription",)

    def __str__(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )

    @property
    def est_mineur(self) -> bool:
        return self.age < 18

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()

    def clean(self):
        errors = {}
        if self.date_naissance:
            if self.age < 14:
                errors["date_naissance"] = "Le candidat doit être âgé d'au moins 14 ans."

        if self.classe_niveau not in dict(self.CLASSE_CHOICES):
            errors["classe_niveau"] = "Classe/Niveau invalide."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.numero_dossier:
            self.numero_dossier = f"AFTEC2026-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class NotesAcademiques(models.Model):
    DIPLOMA_CHOICES = (
        ("CEP", "CEP"),
        ("BEPC", "BEPC"),
        ("CAP", "CAP"),
        ("DTI", "DTI"),
        ("BAC", "BAC"),
        ("DUT", "DUT"),
        ("LICENCE", "LICENCE"),
        ("MASTER", "MASTER"),
    )

    candidat = models.OneToOneField(Candidat, on_delete=models.CASCADE, related_name="notes")
    moyenne_generale_an1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    moyenne_generale_an2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    moyenne_maths_an1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    moyenne_maths_an2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    moyenne_physique_an1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    moyenne_physique_an2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(20)])
    diplome_plus_eleve = models.CharField(max_length=20, choices=DIPLOMA_CHOICES, blank=True)

    def __str__(self):
        return f"Notes de {self.candidat.nom_complet}"


class Documents(models.Model):
    candidat = models.OneToOneField(Candidat, on_delete=models.CASCADE, related_name="documents")
    piece_identite = models.FileField(upload_to="documents/pieces/", validators=[validate_file_extension, validate_file_size])
    bulletin_an1 = models.FileField(upload_to="documents/bulletins/", blank=True, validators=[validate_file_extension, validate_file_size])
    bulletin_an2 = models.FileField(upload_to="documents/bulletins/", blank=True, validators=[validate_file_extension, validate_file_size])
    lettre_motivation = models.FileField(upload_to="documents/motivation/", validators=[validate_file_extension, validate_file_size])
    lettre_recommandation = models.FileField(upload_to="documents/recommandation/", blank=True, validators=[validate_file_extension, validate_file_size])
    attestation_diplome = models.FileField(upload_to="documents/diplomes/", blank=True, validators=[validate_file_extension, validate_file_size])
    dernier_releve_notes = models.FileField(upload_to="documents/releves/", blank=True, validators=[validate_file_extension, validate_file_size])
    autorisation_parentale = models.FileField(upload_to="documents/autorisation/", blank=True, validators=[validate_file_extension, validate_file_size])

    def clean(self):
        errors = {}
        is_professionnel = self.candidat.classe_niveau == "AUTRE"
        if is_professionnel:
            if not self.attestation_diplome:
                errors["attestation_diplome"] = "Ce document est obligatoire pour les professionnels."
            if not self.dernier_releve_notes:
                errors["dernier_releve_notes"] = "Ce document est obligatoire pour les professionnels."
        else:
            if not self.bulletin_an1:
                errors["bulletin_an1"] = "Ce bulletin est obligatoire pour ce niveau."
            if not self.bulletin_an2:
                errors["bulletin_an2"] = "Ce bulletin est obligatoire pour ce niveau."

        if self.candidat.est_mineur and not self.autorisation_parentale:
            errors["autorisation_parentale"] = "Une autorisation parentale est obligatoire pour les mineurs."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Documents de {self.candidat.nom_complet}"


class Consentement(models.Model):
    candidat = models.OneToOneField(Candidat, on_delete=models.CASCADE, related_name="consentement")
    consent_donnees_personnelles = models.BooleanField(default=False)
    consent_reglement = models.BooleanField(default=False)
    consent_selection = models.BooleanField(default=False)
    consent_photos_videos = models.BooleanField(default=False)
    consent_autorisation_parentale_declaree = models.BooleanField(default=False)
    consent_engagement_presence = models.BooleanField(default=False)

    def clean(self):
        errors = {}
        required = [
            "consent_donnees_personnelles",
            "consent_reglement",
            "consent_selection",
            "consent_photos_videos",
            "consent_engagement_presence",
        ]
        for field_name in required:
            if not getattr(self, field_name):
                errors[field_name] = "Ce consentement est obligatoire."

        if self.candidat.est_mineur and not self.consent_autorisation_parentale_declaree:
            errors["consent_autorisation_parentale_declaree"] = "La déclaration parentale est obligatoire pour les mineurs."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Consentements de {self.candidat.nom_complet}"


class QuizQuestion(models.Model):
    CATEGORY_CHOICES = (
        ("electronique", "Électronique"),
        ("mathematiques", "Mathématiques"),
        ("informatique", "Informatique"),
        ("ia", "Intelligence Artificielle"),
        ("entrepreneuriat", "Entrepreneuriat"),
        ("divers", "Divers / Culture Tech"),
    )

    categorie = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    ordre = models.PositiveIntegerField()
    question = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    bonne_reponse = models.CharField(max_length=1, choices=(("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")))

    class Meta:
        ordering = ("categorie", "ordre")
        unique_together = ("categorie", "ordre")

    def __str__(self):
        return f"[{self.get_categorie_display()}] Q{self.ordre}"


class QuizReponse(models.Model):
    candidat = models.OneToOneField(Candidat, on_delete=models.CASCADE, related_name="quiz")
    score_electronique = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_mathematiques = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_informatique = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_ia = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_entrepreneuriat = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_divers = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    score_total = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(30)])
    reponses_json = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        self.score_total = (
            self.score_electronique
            + self.score_mathematiques
            + self.score_informatique
            + self.score_ia
            + self.score_entrepreneuriat
            + self.score_divers
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Quiz de {self.candidat.nom_complet} ({self.score_total}/30)"


class StatutCandidat(models.Model):
    STATUT_CHOICES = (
        ("EN_ATTENTE", "En attente"),
        ("RETENU", "Retenu"),
        ("LISTE_ATTENTE", "Liste d'attente"),
        ("REJETE", "Rejeté"),
    )

    candidat = models.OneToOneField(Candidat, on_delete=models.CASCADE, related_name="statut")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="EN_ATTENTE")
    motif_rejet = models.TextField(blank=True)
    commentaire_jury = models.TextField(blank=True)
    note_motivation = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0), MaxValueValidator(10)])
    date_decision = models.DateTimeField(auto_now=True)
    score_global_selection = models.FloatField(default=0.0)
    email_envoye = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        notes = getattr(self.candidat, "notes", None)
        quiz = getattr(self.candidat, "quiz", None)

        moyenne_maths_an2 = float(notes.moyenne_maths_an2) if notes and notes.moyenne_maths_an2 is not None else 0.0
        moyenne_physique_an2 = float(notes.moyenne_physique_an2) if notes and notes.moyenne_physique_an2 is not None else 0.0
        score_quiz_total = float(quiz.score_total) if quiz else 0.0
        note_motivation = float(self.note_motivation or 0)

        self.score_global_selection = (
            moyenne_maths_an2 * 1
            + moyenne_physique_an2 * 0.5
            + score_quiz_total * 2
            + note_motivation
        )
        self.score_global_selection = round(min(self.score_global_selection, 100), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidat.nom_complet} - {self.get_statut_display()}"
