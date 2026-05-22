from __future__ import annotations

import uuid
from datetime import date
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .challenges_data import (
    CHALLENGE_QCM_DATA,
    OPTION_FIELDS,
    normalize_question_payload,
    option_has_answer_marker,
    strip_answer_markers,
)


def validate_file_size(file_obj):
    max_size = 5 * 1024 * 1024
    if file_obj.size > max_size:
        raise ValidationError("La taille du fichier ne doit pas dépasser 5 Mo.")


def validate_file_extension(file_obj):
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    name = file_obj.name.lower()
    if not any(name.endswith(ext) for ext in allowed_extensions):
        raise ValidationError("Format non autorisé. Utilisez PDF, JPG ou PNG.")


def validate_pdf_extension(file_obj):
    name = (file_obj.name or "").lower()
    if not name.endswith(".pdf"):
        raise ValidationError("Seuls les fichiers PDF sont autorisés.")


class Candidat(models.Model):
    SECONDARY_LEVELS = {"4EME", "3EME", "2NDE", "1ERE", "TLE"}
    HIGHER_AND_PRO_LEVELS = {"L1", "L2", "L3", "M1", "M2", "AUTRE"}
    SECONDARY_QUIZ_CATEGORIES = ("physique", "mathematiques")
    HIGHER_AND_PRO_QUIZ_CATEGORIES = ("informatique", "ia", "entrepreneuriat", "divers")

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
        constraints = [
            models.UniqueConstraint(
                Lower("nom"),
                Lower("prenom"),
                name="uniq_candidat_nom_prenom_ci",
            )
        ]

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

    @classmethod
    def quiz_categories_for_level(cls, classe_niveau: str | None) -> tuple[str, ...]:
        if classe_niveau in cls.SECONDARY_LEVELS:
            return cls.SECONDARY_QUIZ_CATEGORIES
        if classe_niveau in cls.HIGHER_AND_PRO_LEVELS:
            return cls.HIGHER_AND_PRO_QUIZ_CATEGORIES
        return ()

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
        ("physique", "Physique"),
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
    score_physique = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    score_mathematiques = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    score_informatique = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    score_ia = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    score_entrepreneuriat = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    score_divers = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    quiz_elapsed_seconds = models.PositiveIntegerField(default=0)
    score_total = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(40)])
    reponses_json = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        self.score_total = (
            self.score_physique
            + self.score_mathematiques
            + self.score_informatique
            + self.score_ia
            + self.score_entrepreneuriat
            + self.score_divers
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Quiz de {self.candidat.nom_complet} ({self.score_total} points)"


class ChallengePortalSettings(models.Model):
    is_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parametre challenges"
        verbose_name_plural = "Parametres challenges"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.order_by("id").first()
        if obj:
            return obj
        return cls.objects.create()

    def __str__(self):
        return "Challenges actifs" if self.is_enabled else "Challenges inactifs"


class Challenge(models.Model):
    DAY_CHOICES = tuple((day, f"Jour {day}") for day in range(3, 11))

    sequence_day = models.PositiveSmallIntegerField(choices=DAY_CHOICES, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sequence_day",)
        verbose_name = "Challenge"
        verbose_name_plural = "Challenges"

    @classmethod
    def bootstrap_defaults(cls, overwrite_existing=False):
        for item in CHALLENGE_QCM_DATA:
            challenge, created = cls.objects.get_or_create(
                sequence_day=item["sequence_day"],
                defaults={
                    "title": item["title"],
                    "description": item.get("description", ""),
                },
            )
            if overwrite_existing and not created and (
                challenge.title != item["title"] or challenge.description != item.get("description", "")
            ):
                challenge.title = item["title"]
                challenge.description = item.get("description", "")
                challenge.save(update_fields=["title", "description", "updated_at"])

            seen_orders = []
            for order, question_data in enumerate(item.get("questions", []), start=1):
                normalized_question = normalize_question_payload(question_data)
                defaults = {
                    "question": normalized_question["question"],
                    "option_a": normalized_question["option_a"],
                    "option_b": normalized_question["option_b"],
                    "option_c": normalized_question["option_c"],
                    "option_d": normalized_question["option_d"],
                    "correct_option": normalized_question["correct"],
                }
                challenge_question, question_created = ChallengeQuestion.objects.get_or_create(
                    challenge=challenge,
                    order=order,
                    defaults=defaults,
                )
                if overwrite_existing and not question_created:
                    update_fields = []
                    for field_name, field_value in defaults.items():
                        if getattr(challenge_question, field_name) != field_value:
                            setattr(challenge_question, field_name, field_value)
                            update_fields.append(field_name)
                    if update_fields:
                        challenge_question.save(update_fields=update_fields)
                seen_orders.append(order)
            if overwrite_existing and seen_orders:
                challenge.questions.exclude(order__in=seen_orders).delete()

        cls.normalize_question_bank()

    @classmethod
    def normalize_question_bank(cls):
        for question in ChallengeQuestion.objects.all():
            update_fields = []
            marked_options = []
            for option_key, field_name in OPTION_FIELDS:
                option_value = getattr(question, field_name)
                if option_has_answer_marker(option_value):
                    marked_options.append(option_key)
                cleaned_option = strip_answer_markers(option_value)
                if cleaned_option != option_value:
                    setattr(question, field_name, cleaned_option)
                    update_fields.append(field_name)

            if len(marked_options) == 1 and question.correct_option != marked_options[0]:
                question.correct_option = marked_options[0]
                update_fields.append("correct_option")

            if update_fields:
                question.save(update_fields=update_fields)

    @classmethod
    def expire_outdated(cls):
        cls.objects.filter(is_published=True, published_until__lt=timezone.now()).update(is_published=False)

    @property
    def is_active_now(self):
        if not self.is_published or not self.published_until:
            return False
        return self.published_until >= timezone.now()

    @property
    def remaining_seconds(self):
        if not self.is_active_now:
            return 0
        return int((self.published_until - timezone.now()).total_seconds())

    def publish_for_48h(self):
        now = timezone.now()
        self.is_published = True
        self.published_at = now
        self.published_until = now + timedelta(hours=48)
        self.save(update_fields=["is_published", "published_at", "published_until", "updated_at"])

    def unpublish(self):
        self.is_published = False
        self.save(update_fields=["is_published", "updated_at"])

    def __str__(self):
        return f"Jour {self.sequence_day} - {self.title}"


class ChallengeSubmission(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="submissions")
    candidat = models.ForeignKey(Candidat, on_delete=models.CASCADE, related_name="challenge_submissions")
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    elapsed_seconds = models.PositiveIntegerField(default=0)
    answers_json = models.JSONField(default=dict, blank=True)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    jury_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("challenge", "candidat")
        ordering = ("challenge__sequence_day", "elapsed_seconds")
        verbose_name = "Soumission challenge"
        verbose_name_plural = "Soumissions challenges"

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    def finalize_submission(self):
        end_time = timezone.now()
        self.submitted_at = end_time
        self.elapsed_seconds = max(0, int((end_time - self.started_at).total_seconds()))

    def __str__(self):
        return f"{self.candidat.nom_complet} | Jour {self.challenge.sequence_day}"


class ChallengeQuestion(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField()
    question = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(
        max_length=1,
        choices=(("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")),
    )

    class Meta:
        ordering = ("order",)
        unique_together = ("challenge", "order")
        verbose_name = "Question challenge"
        verbose_name_plural = "Questions challenges"

    def __str__(self):
        return f"Jour {self.challenge.sequence_day} Q{self.order}"


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

        def _safe_float(value):
            return float(value) if value is not None else 0.0

        score_quiz_total = _safe_float(getattr(quiz, "score_total", 0.0))
        note_motivation = _safe_float(self.note_motivation)
        q_score = (score_quiz_total / 20.0) * 100.0
        m_score = (note_motivation / 10.0) * 100.0
        level = self.candidat.classe_niveau

        if level in Candidat.SECONDARY_LEVELS:
            academic_values = [
                _safe_float(getattr(notes, "moyenne_generale_an1", None)),
                _safe_float(getattr(notes, "moyenne_generale_an2", None)),
                _safe_float(getattr(notes, "moyenne_maths_an1", None)),
                _safe_float(getattr(notes, "moyenne_maths_an2", None)),
                _safe_float(getattr(notes, "moyenne_physique_an1", None)),
                _safe_float(getattr(notes, "moyenne_physique_an2", None)),
            ]
            a_score = (sum(academic_values) / 6.0) / 20.0 * 100.0
            score_global = 0.50 * a_score + 0.35 * q_score + 0.15 * m_score
        elif level in {"L1", "L2", "L3", "M1", "M2"}:
            academic_values = [
                _safe_float(getattr(notes, "moyenne_generale_an1", None)),
                _safe_float(getattr(notes, "moyenne_generale_an2", None)),
            ]
            a_score = (sum(academic_values) / 2.0) / 20.0 * 100.0
            score_global = 0.40 * a_score + 0.45 * q_score + 0.15 * m_score
        else:
            score_global = 0.60 * q_score + 0.40 * m_score

        self.score_global_selection = round(max(0.0, min(score_global, 100.0)), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidat.nom_complet} - {self.get_statut_display()}"
