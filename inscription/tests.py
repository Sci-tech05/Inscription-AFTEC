from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.options import ModelAdmin
from django.urls import reverse
from django.test import RequestFactory, TestCase

from inscription.admin import CandidatAdmin, StatutCandidatAdmin, aftec_admin_site
from inscription.models import (
    Candidat,
    Challenge,
    ChallengePortalSettings,
    NotesAcademiques,
    QuizReponse,
    StatutCandidat,
)


class CandidatAdminStatusEmailTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = CandidatAdmin(Candidat, aftec_admin_site)
        self.candidat = Candidat.objects.create(
            nom="Doe",
            prenom="Jane",
            date_naissance=date(2004, 1, 1),
            sexe="F",
            telephone="0102030405",
            email="jane.doe@example.com",
            commune_residence="Pobe",
            etablissement="Lycee Test",
            classe_niveau="TLE",
            filiere="Scientifique",
        )

    def test_save_related_sends_email_when_checkbox_checked_and_status_changed(self):
        statut = StatutCandidat.objects.create(candidat=self.candidat, statut="EN_ATTENTE", email_envoye=False)
        statut.statut = "RETENU"
        statut.email_envoye = True

        fake_inline_form = SimpleNamespace(instance=statut, cleaned_data={"DELETE": False})
        fake_formset = SimpleNamespace(model=StatutCandidat, forms=[fake_inline_form])

        with patch.object(ModelAdmin, "save_related", return_value=None), patch(
            "inscription.admin.send_decision_email"
        ) as mocked_send, patch.object(CandidatAdmin, "message_user"):
            self.admin.save_related(self.factory.post("/admin/"), form=None, formsets=[fake_formset], change=True)

        mocked_send.assert_called_once()

    def test_save_related_does_not_resend_when_already_sent_and_status_unchanged(self):
        statut = StatutCandidat.objects.create(candidat=self.candidat, statut="RETENU", email_envoye=True)
        fake_inline_form = SimpleNamespace(instance=statut, cleaned_data={"DELETE": False})
        fake_formset = SimpleNamespace(model=StatutCandidat, forms=[fake_inline_form])

        with patch.object(ModelAdmin, "save_related", return_value=None), patch(
            "inscription.admin.send_decision_email"
        ) as mocked_send, patch.object(CandidatAdmin, "message_user"):
            self.admin.save_related(self.factory.post("/admin/"), form=None, formsets=[fake_formset], change=True)

        mocked_send.assert_not_called()


class StatutCandidatAdminEmailTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = StatutCandidatAdmin(StatutCandidat, aftec_admin_site)
        self.candidat = Candidat.objects.create(
            nom="Roe",
            prenom="John",
            date_naissance=date(2003, 5, 8),
            sexe="M",
            telephone="0101010101",
            email="john.roe@example.com",
            commune_residence="Pobe",
            etablissement="Lycee Test",
            classe_niveau="TLE",
            filiere="Scientifique",
        )

    def test_save_model_sends_email_when_checked(self):
        statut = StatutCandidat.objects.create(candidat=self.candidat, statut="EN_ATTENTE", email_envoye=False)
        statut.statut = "RETENU"
        statut.email_envoye = True

        with patch("inscription.admin.send_decision_email") as mocked_send, patch.object(
            StatutCandidatAdmin, "message_user"
        ):
            self.admin.save_model(self.factory.post("/admin/"), statut, form=None, change=True)

        mocked_send.assert_called_once()


class StatutCandidatScoreFormulaTests(TestCase):
    def _create_candidat(self, email, level):
        return Candidat.objects.create(
            nom="Test",
            prenom="Candidate",
            date_naissance=date(2002, 1, 1),
            sexe="M",
            telephone="0100000000",
            email=email,
            commune_residence="Pobe",
            etablissement="AFTEC",
            classe_niveau=level,
            filiere="STEM",
        )

    def test_secondary_formula(self):
        candidat = self._create_candidat("secondary@example.com", "TLE")
        NotesAcademiques.objects.create(
            candidat=candidat,
            moyenne_generale_an1=Decimal("10.00"),
            moyenne_generale_an2=Decimal("12.00"),
            moyenne_maths_an1=Decimal("14.00"),
            moyenne_maths_an2=Decimal("16.00"),
            moyenne_physique_an1=Decimal("8.00"),
            moyenne_physique_an2=Decimal("10.00"),
        )
        QuizReponse.objects.create(
            candidat=candidat,
            score_physique=8,
            score_mathematiques=7,
            score_informatique=0,
            score_ia=0,
            score_entrepreneuriat=0,
            score_divers=0,
        )

        statut = StatutCandidat.objects.create(
            candidat=candidat,
            note_motivation=Decimal("7.00"),
        )
        self.assertEqual(statut.score_global_selection, 65.92)

    def test_licence_master_formula(self):
        candidat = self._create_candidat("higher@example.com", "L3")
        NotesAcademiques.objects.create(
            candidat=candidat,
            moyenne_generale_an1=Decimal("14.00"),
            moyenne_generale_an2=Decimal("16.00"),
        )
        QuizReponse.objects.create(
            candidat=candidat,
            score_physique=0,
            score_mathematiques=0,
            score_informatique=5,
            score_ia=4,
            score_entrepreneuriat=5,
            score_divers=4,
        )

        statut = StatutCandidat.objects.create(
            candidat=candidat,
            note_motivation=Decimal("8.00"),
        )
        self.assertEqual(statut.score_global_selection, 82.5)

    def test_professional_formula(self):
        candidat = self._create_candidat("pro@example.com", "AUTRE")
        QuizReponse.objects.create(
            candidat=candidat,
            score_physique=0,
            score_mathematiques=0,
            score_informatique=3,
            score_ia=3,
            score_entrepreneuriat=3,
            score_divers=3,
        )

        statut = StatutCandidat.objects.create(
            candidat=candidat,
            note_motivation=Decimal("9.00"),
        )
        self.assertEqual(statut.score_global_selection, 72.0)


class ChallengesPortalTests(TestCase):
    def setUp(self):
        self.candidat = Candidat.objects.create(
            nom="Doe",
            prenom="Jane",
            date_naissance=date(2004, 1, 1),
            sexe="F",
            telephone="0102030405",
            email="challenge.jane@example.com",
            commune_residence="Pobe",
            etablissement="Lycee Test",
            classe_niveau="TLE",
            filiere="Scientifique",
        )
        self.settings_obj = ChallengePortalSettings.get_solo()
        self.settings_obj.is_enabled = True
        self.settings_obj.save(update_fields=["is_enabled", "updated_at"])
        Challenge.bootstrap_defaults()

    def test_challenge_portal_redirects_to_login_when_not_connected(self):
        response = self.client.get(reverse("inscription:challenges_portal"), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("inscription:challenges_login"), response.url)

    def test_challenge_login_accepts_valid_credentials(self):
        response = self.client.post(
            reverse("inscription:challenges_login"),
            {
                "nom_complet": self.candidat.nom_complet,
                "numero_dossier": self.candidat.numero_dossier,
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("inscription:challenges_portal"))
        session = self.client.session
        self.assertEqual(session.get("challenge_candidate_id"), self.candidat.id)
