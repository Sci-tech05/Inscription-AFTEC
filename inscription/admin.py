from __future__ import annotations

import csv
import json
from datetime import date, timedelta

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Candidat, Consentement, Documents, NotesAcademiques, QuizQuestion, QuizReponse, StatutCandidat
from .services import send_decision_email


class AgeRangeFilter(admin.SimpleListFilter):
    title = "Tranche d'âge"
    parameter_name = "age_range"

    def lookups(self, request, model_admin):
        return (
            ("14_17", "14-17 ans"),
            ("18_21", "18-21 ans"),
            ("22_25", "22-25 ans"),
            ("26_plus", "26 ans et +"),
        )

    def queryset(self, request, queryset):
        today = date.today()

        def birthdate_range(min_age, max_age):
            max_birth = today.replace(year=today.year - min_age)
            min_birth = today.replace(year=today.year - max_age - 1) + timedelta(days=1)
            return min_birth, max_birth

        value = self.value()
        if value == "14_17":
            start, end = birthdate_range(14, 17)
            return queryset.filter(date_naissance__range=(start, end))
        if value == "18_21":
            start, end = birthdate_range(18, 21)
            return queryset.filter(date_naissance__range=(start, end))
        if value == "22_25":
            start, end = birthdate_range(22, 25)
            return queryset.filter(date_naissance__range=(start, end))
        if value == "26_plus":
            end = today.replace(year=today.year - 26)
            return queryset.filter(date_naissance__lte=end)
        return queryset


class NotesAcademiquesInline(admin.StackedInline):
    model = NotesAcademiques
    extra = 0
    verbose_name_plural = "Notes"


class DocumentsInline(admin.StackedInline):
    model = Documents
    extra = 0
    verbose_name_plural = "Documents"
    readonly_fields = (
        "piece_identite_link",
        "bulletin_an1_link",
        "bulletin_an2_link",
        "lettre_motivation_link",
        "lettre_recommandation_link",
        "autorisation_parentale_link",
    )

    fields = (
        "piece_identite",
        "piece_identite_link",
        "bulletin_an1",
        "bulletin_an1_link",
        "bulletin_an2",
        "bulletin_an2_link",
        "lettre_motivation",
        "lettre_motivation_link",
        "lettre_recommandation",
        "lettre_recommandation_link",
        "autorisation_parentale",
        "autorisation_parentale_link",
    )

    @staticmethod
    def _file_link(file_field):
        if not file_field:
            return "-"
        return format_html('<a href="{}" target="_blank">Télécharger</a>', file_field.url)

    def piece_identite_link(self, obj):
        return self._file_link(obj.piece_identite)

    def bulletin_an1_link(self, obj):
        return self._file_link(obj.bulletin_an1)

    def bulletin_an2_link(self, obj):
        return self._file_link(obj.bulletin_an2)

    def lettre_motivation_link(self, obj):
        return self._file_link(obj.lettre_motivation)

    def lettre_recommandation_link(self, obj):
        return self._file_link(obj.lettre_recommandation)

    def autorisation_parentale_link(self, obj):
        return self._file_link(obj.autorisation_parentale)


class QuizReponseInline(admin.StackedInline):
    model = QuizReponse
    extra = 0
    verbose_name_plural = "Quiz"
    readonly_fields = ("score_total",)


class StatutInline(admin.StackedInline):
    model = StatutCandidat
    extra = 0
    verbose_name_plural = "Décision"


class CandidatAdmin(admin.ModelAdmin):
    list_display = (
        "nom_complet",
        "etablissement",
        "classe_niveau",
        "moyenne_generale_coloree",
        "score_quiz_bar",
        "score_global",
        "statut_badge",
        "date_inscription",
    )
    list_filter = ("statut__statut", "sexe", AgeRangeFilter, "etablissement", "commune_residence")
    search_fields = ("nom", "prenom", "email", "etablissement")
    actions = (
        "marquer_retenus",
        "marquer_rejetes",
        "marquer_liste_attente",
        "exporter_csv",
        "envoyer_notifications_statut",
    )
    inlines = [NotesAcademiquesInline, DocumentsInline, QuizReponseInline, StatutInline]
    list_select_related = ("notes", "quiz", "statut")

    fieldsets = (
        (
            "Profil",
            {
                "fields": (
                    "nom",
                    "prenom",
                    "date_naissance",
                    "sexe",
                    "telephone",
                    "email",
                    "commune_residence",
                    "etablissement",
                    "classe_niveau",
                    "filiere",
                    "numero_dossier",
                )
            },
        ),
    )
    readonly_fields = ("numero_dossier",)

    class Media:
        css = {"all": ("admin/candidat_tabs.css",)}
        js = ("admin/candidat_tabs.js",)

    def save_related(self, request, form, formsets, change):
        previous_states = {}
        for formset in formsets:
            if getattr(formset, "model", None) is not StatutCandidat:
                continue
            for inline_form in formset.forms:
                instance = inline_form.instance
                if instance.pk:
                    previous_states[instance.pk] = StatutCandidat.objects.filter(pk=instance.pk).values(
                        "statut", "email_envoye"
                    ).first()

        super().save_related(request, form, formsets, change)

        sent = 0
        failed = 0
        for formset in formsets:
            if getattr(formset, "model", None) is not StatutCandidat:
                continue
            for inline_form in formset.forms:
                cleaned_data = getattr(inline_form, "cleaned_data", None) or {}
                if cleaned_data.get("DELETE"):
                    continue

                statut_obj = inline_form.instance
                if not statut_obj.pk or not statut_obj.email_envoye:
                    continue

                previous = previous_states.get(statut_obj.pk)
                should_send = previous is None or (not previous["email_envoye"]) or previous["statut"] != statut_obj.statut
                if not should_send:
                    continue

                try:
                    send_decision_email(statut_obj.candidat, statut_obj.statut, commentaire=statut_obj.commentaire_jury)
                    sent += 1
                except Exception:
                    failed += 1
                    statut_obj.email_envoye = False
                    statut_obj.save(update_fields=["email_envoye"])

        if sent:
            self.message_user(request, f"{sent} email(s) envoyé(s) depuis la fiche candidat.", level=messages.SUCCESS)
        if failed:
            self.message_user(
                request,
                f"{failed} email(s) n'ont pas pu être envoyés. La case d'envoi a été décochée automatiquement.",
                level=messages.WARNING,
            )

    @admin.display(description="Nom complet")
    def nom_complet(self, obj):
        return obj.nom_complet

    @admin.display(description="Moyenne générale")
    def moyenne_generale_coloree(self, obj):
        moyenne = getattr(getattr(obj, "notes", None), "moyenne_generale_an2", None)
        if moyenne is None:
            return "-"
        value = float(moyenne)
        color = "#0F9B58" if value >= 12 else "#F5A623" if value >= 10 else "#E94560"
        return format_html('<strong style="color:{}">{}/20</strong>', color, f"{value:.2f}")

    @admin.display(description="Score quiz /30")
    def score_quiz_bar(self, obj):
        score = getattr(getattr(obj, "quiz", None), "score_total", 0)
        pct = int((score / 30) * 100) if score else 0
        color = "#0F9B58" if score >= 20 else "#F5A623" if score >= 12 else "#E94560"
        return format_html(
            '<div style="min-width:170px"><div style="background:#eee;border-radius:999px;height:10px;">'
            '<div style="width:{}%;background:{};height:10px;border-radius:999px;"></div></div><small>{}/30</small></div>',
            pct,
            color,
            score,
        )

    @admin.display(description="Score global")
    def score_global(self, obj):
        statut = getattr(obj, "statut", None)
        if not statut:
            return "-"
        return f"{statut.score_global_selection:.2f}/100"

    @admin.display(description="Statut")
    def statut_badge(self, obj):
        statut = getattr(obj, "statut", None)
        if not statut:
            return "-"
        colors = {
            "EN_ATTENTE": "#16213E",
            "RETENU": "#0F9B58",
            "REJETE": "#E94560",
            "LISTE_ATTENTE": "#F5A623",
        }
        color = colors.get(statut.statut, "#16213E")
        label = statut.get_statut_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:4px 10px;border-radius:999px;font-size:12px;">{}</span>',
            color,
            label,
        )

    def _set_status_and_notify(self, request, queryset, new_status):
        updated = 0
        sent = 0
        failed = 0

        for candidat in queryset:
            statut, _ = StatutCandidat.objects.get_or_create(candidat=candidat)
            statut.statut = new_status
            statut.save()
            updated += 1

            try:
                send_decision_email(candidat, new_status, commentaire=statut.commentaire_jury)
                statut.email_envoye = True
                statut.save(update_fields=["email_envoye", "date_decision", "score_global_selection"])
                sent += 1
            except Exception:
                failed += 1

        level = messages.SUCCESS if failed == 0 else messages.WARNING
        self.message_user(
            request,
            f"{updated} statut(s) mis à jour, {sent} email(s) envoyé(s), {failed} échec(s).",
            level=level,
        )

    @admin.action(description="Marquer comme Retenu(s) + email")
    def marquer_retenus(self, request, queryset):
        self._set_status_and_notify(request, queryset, "RETENU")

    @admin.action(description="Marquer comme Rejeté(s) + email")
    def marquer_rejetes(self, request, queryset):
        self._set_status_and_notify(request, queryset, "REJETE")

    @admin.action(description="Marquer en Liste d'attente + email")
    def marquer_liste_attente(self, request, queryset):
        self._set_status_and_notify(request, queryset, "LISTE_ATTENTE")

    @admin.action(description="Exporter en CSV")
    def exporter_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="candidats_aftec2026.csv"'
        writer = csv.writer(response)
        writer.writerow(["Nom", "Prénom", "Email", "Établissement", "Classe", "Statut", "Score Quiz", "Score Global"])

        for candidat in queryset:
            statut = getattr(candidat, "statut", None)
            quiz = getattr(candidat, "quiz", None)
            writer.writerow(
                [
                    candidat.nom,
                    candidat.prenom,
                    candidat.email,
                    candidat.etablissement,
                    candidat.get_classe_niveau_display(),
                    statut.get_statut_display() if statut else "En attente",
                    quiz.score_total if quiz else 0,
                    statut.score_global_selection if statut else 0,
                ]
            )

        return response

    @admin.action(description="Envoyer email selon le statut actuel")
    def envoyer_notifications_statut(self, request, queryset):
        sent = 0
        failed = 0

        for candidat in queryset:
            statut, _ = StatutCandidat.objects.get_or_create(candidat=candidat)
            try:
                send_decision_email(candidat, statut.statut, commentaire=statut.commentaire_jury)
                statut.email_envoye = True
                statut.save(update_fields=["email_envoye", "date_decision", "score_global_selection"])
                sent += 1
            except Exception:
                failed += 1

        level = messages.SUCCESS if failed == 0 else messages.WARNING
        self.message_user(request, f"{sent} email(s) envoyé(s), {failed} échec(s).", level=level)


class AFTECAdminSite(AdminSite):
    site_header = "AFTEC 2026 Administration"
    site_title = "AFTEC Admin"
    index_title = "Tableau de bord AFTEC"
    index_template = "admin/custom_index.html"
    login_template = "admin/custom_login.html"
    enable_nav_sidebar = False

    def each_context(self, request):
        context = super().each_context(request)

        total = Candidat.objects.count()

        status_counts = {
            item["statut"]: item["total"]
            for item in StatutCandidat.objects.values("statut").annotate(total=Count("id"))
        }
        sexe_counts = {item["sexe"]: item["total"] for item in Candidat.objects.values("sexe").annotate(total=Count("id"))}
        classe_counts = {
            item["classe_niveau"]: item["total"]
            for item in Candidat.objects.values("classe_niveau").annotate(total=Count("id"))
        }

        by_day_qs = (
            Candidat.objects.annotate(jour=TruncDate("date_inscription"))
            .values("jour")
            .annotate(total=Count("id"))
            .order_by("jour")
        )

        quiz_avg = QuizReponse.objects.aggregate(
            electronique=Avg("score_electronique"),
            mathematiques=Avg("score_mathematiques"),
            informatique=Avg("score_informatique"),
            ia=Avg("score_ia"),
            entrepreneuriat=Avg("score_entrepreneuriat"),
            divers=Avg("score_divers"),
        )

        top10 = StatutCandidat.objects.select_related("candidat").order_by("-score_global_selection")[:10]

        context["dashboard_data"] = json.dumps(
            {
                "total": total,
                "statuts": {
                    "labels": ["En attente", "Retenu", "Liste d'attente", "Rejeté"],
                    "values": [
                        status_counts.get("EN_ATTENTE", 0),
                        status_counts.get("RETENU", 0),
                        status_counts.get("LISTE_ATTENTE", 0),
                        status_counts.get("REJETE", 0),
                    ],
                },
                "sexe": {
                    "labels": ["Masculin", "Féminin"],
                    "values": [sexe_counts.get("M", 0), sexe_counts.get("F", 0)],
                },
                "classe": {
                    "labels": [dict(Candidat.CLASSE_CHOICES).get(key, key) for key in classe_counts.keys()],
                    "values": list(classe_counts.values()),
                },
                "evolution": {
                    "labels": [str(item["jour"]) for item in by_day_qs],
                    "values": [item["total"] for item in by_day_qs],
                },
                "quiz_avg": {
                    "labels": ["Électronique", "Mathématiques", "Informatique", "IA", "Entrepreneuriat", "Divers"],
                    "values": [
                        round(float(quiz_avg.get("electronique") or 0), 2),
                        round(float(quiz_avg.get("mathematiques") or 0), 2),
                        round(float(quiz_avg.get("informatique") or 0), 2),
                        round(float(quiz_avg.get("ia") or 0), 2),
                        round(float(quiz_avg.get("entrepreneuriat") or 0), 2),
                        round(float(quiz_avg.get("divers") or 0), 2),
                    ],
                },
                "top10": [{"nom": item.candidat.nom_complet, "score": item.score_global_selection} for item in top10],
            }
        )
        context["kcomat"] = settings.KCOMAT_INFO

        return context


aftec_admin_site = AFTECAdminSite(name="aftec_admin")
aftec_admin_site.register(Candidat, CandidatAdmin)
aftec_admin_site.register(NotesAcademiques)
aftec_admin_site.register(Documents)
aftec_admin_site.register(Consentement)
aftec_admin_site.register(QuizQuestion)
aftec_admin_site.register(QuizReponse)


@admin.register(StatutCandidat, site=aftec_admin_site)
class StatutCandidatAdmin(admin.ModelAdmin):
    list_display = ("candidat", "statut", "email_envoye", "date_decision", "score_global_selection")
    list_filter = ("statut", "email_envoye", "date_decision")
    search_fields = ("candidat__nom", "candidat__prenom", "candidat__email", "candidat__numero_dossier")
    autocomplete_fields = ("candidat",)

    def save_model(self, request, obj, form, change):
        previous = None
        if change and obj.pk:
            previous = StatutCandidat.objects.filter(pk=obj.pk).values("statut", "email_envoye").first()

        super().save_model(request, obj, form, change)

        should_send = obj.email_envoye and (
            previous is None or (not previous["email_envoye"]) or previous["statut"] != obj.statut
        )
        if not should_send:
            return

        try:
            send_decision_email(obj.candidat, obj.statut, commentaire=obj.commentaire_jury)
            self.message_user(request, "Email de décision envoyé au candidat.", level=messages.SUCCESS)
        except Exception:
            obj.email_envoye = False
            obj.save(update_fields=["email_envoye"])
            self.message_user(
                request,
                "Échec d'envoi email. La case 'email envoyé' a été décochée automatiquement.",
                level=messages.WARNING,
            )
