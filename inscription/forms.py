from __future__ import annotations

from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import Candidat, NotesAcademiques, QuizQuestion


class DateInput(forms.DateInput):
    input_type = "date"


class InscriptionMultiStepForm(forms.Form):
    HIGHER_LEVEL_CLASSES = {"L1", "L2", "L3", "M1", "M2"}
    PROFESSIONAL_CLASS = "AUTRE"

    # Etape 1 : Consentements
    consent_donnees_personnelles = forms.BooleanField(required=True, label="J'accepte le traitement de mes données personnelles")
    consent_selection = forms.BooleanField(required=True, label="Je comprends et accepte les critères de sélection sur mérite")
    consent_reglement = forms.BooleanField(required=True, label="J'accepte le règlement intérieur de la formation AFTEC 2026")
    consent_photos_videos = forms.BooleanField(required=True, label="J'autorise KcoMat à utiliser mon image (photos/vidéos)")
    consent_engagement_presence = forms.BooleanField(required=True, label="Je m'engage à participer aux 15 jours de la formation si sélectionné(e)")
    consent_autorisation_parentale_declaree = forms.BooleanField(
        required=False,
        label="Je déclare avoir l'autorisation de mes parents/tuteurs légaux",
    )

    # Etape 2 : Candidat
    nom = forms.CharField(max_length=120)
    prenom = forms.CharField(max_length=120)
    date_naissance = forms.DateField(widget=DateInput())
    sexe = forms.ChoiceField(choices=Candidat.SEXE_CHOICES)
    telephone = forms.CharField(max_length=30)
    email = forms.EmailField()
    commune_residence = forms.CharField(max_length=120)
    etablissement = forms.CharField(max_length=255)
    classe_niveau = forms.ChoiceField(choices=Candidat.CLASSE_CHOICES)
    filiere = forms.CharField(max_length=120)

    # Etape 3 : Notes
    moyenne_generale_an1 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        label="Moyenne générale Année passée",
    )
    moyenne_generale_an2 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        label="Moyenne générale S1 Année actuel",
    )
    moyenne_maths_an1 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        required=False,
        label="Moyenne maths Semestre 1",
    )
    moyenne_maths_an2 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        required=False,
        label="Moyenne maths Semestre 2",
    )
    moyenne_physique_an1 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        required=False,
        label="Moyenne physique Semestre 1",
    )
    moyenne_physique_an2 = forms.DecimalField(
        min_value=0,
        max_value=20,
        decimal_places=2,
        required=False,
        label="Moyenne physique Semestre 2",
    )
    diplome_plus_eleve = forms.ChoiceField(
        choices=(("", "Sélectionnez un diplôme"), *NotesAcademiques.DIPLOMA_CHOICES),
        required=False,
        label="Diplôme le plus élevé",
    )
    attestation_diplome = forms.FileField(required=False, label="Attestation du diplôme")
    dernier_releve_notes = forms.FileField(required=False, label="Dernier relevé de notes")

    # Etape 4 : Lettre de motivation
    lettre_motivation = forms.FileField(required=True)

    # Etape 5 : Documents
    piece_identite = forms.FileField(required=True)
    bulletin_an1 = forms.FileField(required=False, label="Bulletin Année passée")
    bulletin_an2 = forms.FileField(required=False, label="Bulletin S1 année actuelle")
    lettre_recommandation = forms.FileField(required=False, label="Lettre recommandation (facultative)")
    autorisation_parentale = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(QuizQuestion.objects.all())

        for question in self.questions:
            field_name = f"question_{question.id}"
            self.fields[field_name] = forms.ChoiceField(
                label=question.question,
                choices=(
                    ("A", question.option_a),
                    ("B", question.option_b),
                    ("C", question.option_c),
                    ("D", question.option_d),
                ),
                widget=forms.RadioSelect,
                required=True,
            )

        for _, field in self.fields.items():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            if isinstance(field.widget, forms.RadioSelect):
                css = "quiz-radio-input"
            field.widget.attrs.setdefault("class", css)

    @staticmethod
    def _age(birth_date):
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Candidat.objects.filter(email__iexact=email).exists():
            raise ValidationError("Une candidature existe déjà avec cette adresse email.")
        return email

    def clean_date_naissance(self):
        birth_date = self.cleaned_data["date_naissance"]
        if self._age(birth_date) < 14:
            raise ValidationError("Le candidat doit être âgé d'au moins 14 ans.")
        return birth_date

    def clean(self):
        cleaned_data = super().clean()

        date_naissance = cleaned_data.get("date_naissance")
        classe_niveau = cleaned_data.get("classe_niveau")

        required_consents = [
            "consent_donnees_personnelles",
            "consent_selection",
            "consent_reglement",
            "consent_photos_videos",
            "consent_engagement_presence",
        ]
        for field_name in required_consents:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, "Ce consentement est obligatoire.")

        is_professional = classe_niveau == self.PROFESSIONAL_CLASS

        if is_professional:
            required_professional_fields = [
                "diplome_plus_eleve",
                "attestation_diplome",
                "dernier_releve_notes",
            ]
            for field_name in required_professional_fields:
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, "Ce champ est obligatoire pour les professionnels.")

            for field_name in [
                "moyenne_generale_an1",
                "moyenne_generale_an2",
                "moyenne_maths_an1",
                "moyenne_maths_an2",
                "moyenne_physique_an1",
                "moyenne_physique_an2",
            ]:
                cleaned_data[field_name] = None

            cleaned_data["bulletin_an1"] = None
            cleaned_data["bulletin_an2"] = None
        elif classe_niveau in self.HIGHER_LEVEL_CLASSES:
            required_general_scores = [
                "moyenne_generale_an1",
                "moyenne_generale_an2",
            ]
            for field_name in required_general_scores:
                if cleaned_data.get(field_name) is None:
                    self.add_error(field_name, "Cette moyenne est obligatoire pour ce niveau.")

            if cleaned_data.get("moyenne_maths_an1") is None:
                cleaned_data["moyenne_maths_an1"] = cleaned_data.get("moyenne_generale_an1")
            if cleaned_data.get("moyenne_maths_an2") is None:
                cleaned_data["moyenne_maths_an2"] = cleaned_data.get("moyenne_generale_an2")
            if cleaned_data.get("moyenne_physique_an1") is None:
                cleaned_data["moyenne_physique_an1"] = cleaned_data.get("moyenne_generale_an1")
            if cleaned_data.get("moyenne_physique_an2") is None:
                cleaned_data["moyenne_physique_an2"] = cleaned_data.get("moyenne_generale_an2")
        else:
            required_general_scores = [
                "moyenne_generale_an1",
                "moyenne_generale_an2",
            ]
            for field_name in required_general_scores:
                if cleaned_data.get(field_name) is None:
                    self.add_error(field_name, "Cette moyenne est obligatoire pour ce niveau.")

            required_scores = [
                "moyenne_maths_an1",
                "moyenne_maths_an2",
                "moyenne_physique_an1",
                "moyenne_physique_an2",
            ]
            for field_name in required_scores:
                if cleaned_data.get(field_name) is None:
                    self.add_error(field_name, "Cette moyenne est obligatoire pour ce niveau.")

        if not is_professional:
            if not cleaned_data.get("bulletin_an1"):
                self.add_error("bulletin_an1", "Ce document est obligatoire pour ce niveau.")
            if not cleaned_data.get("bulletin_an2"):
                self.add_error("bulletin_an2", "Ce document est obligatoire pour ce niveau.")

        if date_naissance:
            is_minor = self._age(date_naissance) < 18
            if is_minor and not cleaned_data.get("consent_autorisation_parentale_declaree"):
                self.add_error(
                    "consent_autorisation_parentale_declaree",
                    "Cette déclaration est obligatoire pour les candidats mineurs.",
                )
            if is_minor and not cleaned_data.get("autorisation_parentale"):
                self.add_error("autorisation_parentale", "L'autorisation parentale est obligatoire pour les mineurs.")

        return cleaned_data

    def build_quiz_scores(self):
        category_mapping = {
            "electronique": "score_electronique",
            "mathematiques": "score_mathematiques",
            "informatique": "score_informatique",
            "ia": "score_ia",
            "entrepreneuriat": "score_entrepreneuriat",
            "divers": "score_divers",
        }
        scores = {field_name: 0 for field_name in category_mapping.values()}
        raw_answers = {}

        for question in self.questions:
            answer_key = f"question_{question.id}"
            user_answer = self.cleaned_data.get(answer_key)
            raw_answers[str(question.id)] = {
                "question": question.question,
                "categorie": question.categorie,
                "reponse_utilisateur": user_answer,
                "bonne_reponse": question.bonne_reponse,
                "correcte": user_answer == question.bonne_reponse,
            }
            if user_answer == question.bonne_reponse:
                score_field = category_mapping[question.categorie]
                scores[score_field] += 1

        scores["score_total"] = sum(scores.values())
        scores["reponses_json"] = raw_answers
        return scores

    def build_warnings(self):
        warnings = []
        commune = (self.cleaned_data.get("commune_residence") or "").lower()

        zone_terms = ["pobè", "plateau", "kétou", "ketou", "adja", "issaba", "sakete", "sakété"]
        if not any(term in commune for term in zone_terms):
            warnings.append(
                "Votre commune semble hors Pobè et environs. La candidature reste possible, mais la priorité peut être donnée aux résidents locaux."
            )

        return warnings
