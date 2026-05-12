from __future__ import annotations

import csv
from datetime import date, timedelta
from io import BytesIO

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import (
    Candidat,
    Challenge,
    ChallengePortalSettings,
    ChallengeSubmission,
    Consentement,
    Documents,
    NotesAcademiques,
    QuizReponse,
    StatutCandidat,
)
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
        "attestation_diplome_link",
        "dernier_releve_notes_link",
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
        "attestation_diplome",
        "attestation_diplome_link",
        "dernier_releve_notes",
        "dernier_releve_notes_link",
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

    def attestation_diplome_link(self, obj):
        return self._file_link(obj.attestation_diplome)

    def dernier_releve_notes_link(self, obj):
        return self._file_link(obj.dernier_releve_notes)

    def autorisation_parentale_link(self, obj):
        return self._file_link(obj.autorisation_parentale)


class QuizReponseInline(admin.StackedInline):
    model = QuizReponse
    extra = 0
    verbose_name_plural = "Quiz"
    readonly_fields = ("score_total", "quiz_elapsed_seconds")


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
                except Exception as exc:
                    failed += 1
                    statut_obj.email_envoye = False
                    statut_obj.save(update_fields=["email_envoye"])
                    self.message_user(
                        request,
                        f"Échec d'envoi pour {statut_obj.candidat.email}: {exc}",
                        level=messages.WARNING,
                    )

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

    @admin.display(description="Score quiz")
    def score_quiz_bar(self, obj):
        score = getattr(getattr(obj, "quiz", None), "score_total", 0)
        category_max = {
            "physique": 10,
            "mathematiques": 10,
            "informatique": 5,
            "ia": 5,
            "entrepreneuriat": 5,
            "divers": 5,
        }
        categories = Candidat.quiz_categories_for_level(obj.classe_niveau)
        max_score = sum(category_max.get(category, 0) for category in categories) or 1
        pct = int((score / max_score) * 100) if score else 0
        ratio = score / max_score
        color = "#0F9B58" if ratio >= 0.7 else "#F5A623" if ratio >= 0.5 else "#E94560"
        return format_html(
            '<div style="min-width:170px"><div style="background:#eee;border-radius:999px;height:10px;">'
            '<div style="width:{}%;background:{};height:10px;border-radius:999px;"></div></div><small>{}/{}</small></div>',
            pct,
            color,
            score,
            max_score,
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
            except Exception as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Échec d'envoi pour {candidat.email}: {exc}",
                    level=messages.WARNING,
                )

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
            except Exception as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Échec d'envoi pour {candidat.email}: {exc}",
                    level=messages.WARNING,
                )

        level = messages.SUCCESS if failed == 0 else messages.WARNING
        self.message_user(request, f"{sent} email(s) envoyé(s), {failed} échec(s).", level=level)


class AFTECAdminSite(AdminSite):
    site_header = "AFTEC 2026 Administration"
    site_title = "AFTEC Admin"
    index_title = "Tableau de bord AFTEC"
    index_template = "admin/custom_index.html"
    login_template = "admin/custom_login.html"
    enable_nav_sidebar = True

    @staticmethod
    def _format_duration(seconds):
        total = int(seconds or 0)
        minutes = total // 60
        remainder = total % 60
        return f"{minutes:02d}:{remainder:02d}"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "challenges/",
                self.admin_view(self.challenges_hub),
                name="challenges_hub",
            ),
            path(
                "exports/candidats-retenus/pdf/",
                self.admin_view(self.export_retenus_pdf),
                name="retained_candidates_pdf",
            )
        ]
        return custom_urls + urls

    def challenges_hub(self, request):
        Challenge.bootstrap_defaults()
        Challenge.expire_outdated()
        settings_obj = ChallengePortalSettings.get_solo()

        if request.method == "POST":
            action = (request.POST.get("action") or "").strip()
            if action == "toggle_portal":
                desired_value = request.POST.get("enabled") == "1"
                settings_obj.is_enabled = desired_value
                settings_obj.save(update_fields=["is_enabled", "updated_at"])
                label = "activé" if desired_value else "désactivé"
                self.message_user(request, f"Onglet Challenges {label} côté utilisateurs.", level=messages.SUCCESS)
                return redirect("admin:challenges_hub")

            if action in {"publish_challenge", "unpublish_challenge"}:
                challenge_id = request.POST.get("challenge_id")
                challenge = Challenge.objects.filter(pk=challenge_id).first()
                if not challenge:
                    self.message_user(request, "Challenge introuvable.", level=messages.WARNING)
                    return redirect("admin:challenges_hub")
                if action == "publish_challenge":
                    if not challenge.challenge_pdf:
                        self.message_user(
                            request,
                            "Ajoutez d'abord le PDF du challenge avant publication.",
                            level=messages.WARNING,
                        )
                        return redirect("admin:challenges_hub")
                    challenge.publish_for_48h()
                    self.message_user(
                        request,
                        f"{challenge.title} publié pour 48h (jusqu'au {challenge.published_until:%d/%m/%Y %H:%M}).",
                        level=messages.SUCCESS,
                    )
                else:
                    challenge.unpublish()
                    self.message_user(request, f"{challenge.title} retiré de l'espace participants.", level=messages.SUCCESS)
                return redirect("admin:challenges_hub")

        now = timezone.now()
        challenges = list(Challenge.objects.all().order_by("sequence_day"))
        published_ids = [item.id for item in challenges if item.is_published and item.published_until and item.published_until >= now]

        rankings = {}
        if published_ids:
            submissions = (
                ChallengeSubmission.objects.select_related("candidat", "challenge")
                .filter(challenge_id__in=published_ids, submitted_at__isnull=False)
                .order_by("challenge__sequence_day", "elapsed_seconds", "submitted_at")
            )
            for submission in submissions:
                rankings.setdefault(submission.challenge_id, []).append(submission)
            for challenge_id, grouped_submissions in rankings.items():
                grouped_submissions.sort(
                    key=lambda item: (
                        item.score is None,
                        -(float(item.score) if item.score is not None else 0.0),
                        item.elapsed_seconds,
                        item.submitted_at or timezone.now(),
                    )
                )
                rankings[challenge_id] = [
                    {
                        "nom": item.candidat.nom_complet,
                        "score": "-" if item.score is None else f"{float(item.score):.2f}",
                        "temps": self._format_duration(item.elapsed_seconds),
                    }
                    for item in grouped_submissions
                ]
        challenge_rankings = [
            {"challenge": challenge, "rows": rankings.get(challenge.id, [])}
            for challenge in challenges
            if challenge.is_published and challenge.published_until and challenge.published_until >= now
        ]

        context = dict(
            self.each_context(request),
            title="Challenges",
            settings_obj=settings_obj,
            challenges=challenges,
            challenge_rankings=challenge_rankings,
            now=now,
        )
        return render(request, "admin/challenges_hub.html", context)

    def export_retenus_pdf(self, request):
        retenus = (
            StatutCandidat.objects.select_related("candidat", "candidat__quiz")
            .filter(statut="RETENU")
            .order_by("-score_global_selection", "candidat__nom", "candidat__prenom")
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.1 * cm,
            leftMargin=1.1 * cm,
            topMargin=1.0 * cm,
            bottomMargin=2.2 * cm,
        )
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="HeaderTitle",
                parent=styles["Heading1"],
                textColor=colors.white,
                fontName="Helvetica-Bold",
                fontSize=15.5,
                leading=18,
                alignment=1,
            )
        )
        styles.add(
            ParagraphStyle(
                name="HeaderSubtitle",
                parent=styles["Normal"],
                textColor=colors.HexColor("#E8F1FF"),
                fontSize=9.2,
                leading=11.5,
                alignment=1,
            )
        )
        styles.add(
            ParagraphStyle(
                name="BodyMuted",
                parent=styles["Normal"],
                textColor=colors.HexColor("#5C6470"),
                fontSize=9.2,
                leading=11.5,
                alignment=1,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CellText",
                parent=styles["Normal"],
                textColor=colors.HexColor("#1F2A37"),
                fontSize=8.7,
                leading=10.6,
                alignment=1,
            )
        )

        def _fit_logo(path_obj, max_width_cm, max_height_cm):
            if not path_obj.exists():
                return ""
            logo = RLImage(str(path_obj))
            max_w = max_width_cm * cm
            max_h = max_height_cm * cm
            ratio = min(max_w / float(logo.imageWidth), max_h / float(logo.imageHeight))
            logo.drawWidth = float(logo.imageWidth) * ratio
            logo.drawHeight = float(logo.imageHeight) * ratio
            logo.hAlign = "CENTER"
            return logo

        logo_aftec = settings.BASE_DIR / "static" / "img" / "logo-aftec.png"
        logo_kcomat = settings.BASE_DIR / "static" / "img" / "logo-kcomat.jpeg"
        left_logo = _fit_logo(logo_aftec, 3.6, 1.6)
        right_logo = _fit_logo(logo_kcomat, 3.6, 1.6)

        footer_line_1 = (
            f"Organisation: {settings.KCOMAT_INFO['name']} | IFU: {settings.KCOMAT_INFO['ifu']} | "
            f"RCCM: {settings.KCOMAT_INFO['rccm']}"
        )
        footer_line_2 = (
            f"Contact officiel: {settings.KCOMAT_INFO['phone']} | {settings.KCOMAT_INFO['email']} | "
            f"{settings.KCOMAT_INFO['address']}"
        )

        def _draw_fixed_footer(canvas, _doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 9.2)
            canvas.setFillColor(colors.HexColor("#5C6470"))
            center_x = A4[0] / 2
            canvas.drawCentredString(center_x, 1.25 * cm, footer_line_1)
            canvas.drawCentredString(center_x, 0.86 * cm, footer_line_2)
            canvas.restoreState()

        elements = []
        header_text = [
            Paragraph("LISTE OFFICIELLE DES CANDIDATS RETENUS", styles["HeaderTitle"]),
            Paragraph("AFTEC 2026 | Session du 03 au 21 Août 2026 | Pobè, Bénin", styles["HeaderSubtitle"]),
            Paragraph(f"Date d'édition: {date.today().strftime('%d/%m/%Y')}", styles["HeaderSubtitle"]),
            Paragraph(f"Total retenus: <b>{retenus.count()}</b>", styles["HeaderSubtitle"]),
        ]
        header_total_width = A4[0] - doc.leftMargin - doc.rightMargin
        side_col_width = 4.1 * cm
        header_table = Table(
            [[left_logo, header_text, right_logo]],
            colWidths=[side_col_width, header_total_width - (2 * side_col_width), side_col_width],
            hAlign="CENTER",
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0E2A47")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0A2039")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 0.35 * cm))

        elements.append(
            Paragraph(
                "Classement des candidats retenus",
                ParagraphStyle(
                    name="SectionTitleRetenus",
                    parent=styles["Heading3"],
                    textColor=colors.HexColor("#163C5B"),
                    fontName="Helvetica-Bold",
                    fontSize=10.8,
                    spaceAfter=6,
                ),
            )
        )

        table_data = [["#", "Nom et Prenoms", "Niveau", "Contact"]]
        for idx, statut in enumerate(retenus, start=1):
            candidat = statut.candidat
            table_data.append(
                [
                    str(idx),
                    candidat.nom_complet,
                    candidat.get_classe_niveau_display(),
                    candidat.telephone,
                ]
            )

        if len(table_data) == 1:
            table_data.append(
                [
                    "-",
                    "Aucun candidat retenu pour le moment.",
                    "-",
                    "-",
                ]
            )

        def _compute_col_widths(rows, available_width):
            min_widths = [0.9 * cm, 5.8 * cm, 2.8 * cm, 3.3 * cm]
            max_widths = [1.4 * cm, 9.2 * cm, 4.3 * cm, 5.2 * cm]
            widths = []
            for col_idx in range(len(rows[0])):
                max_text = max(str(r[col_idx]) for r in rows)
                font_name = "Helvetica-Bold" if col_idx == 0 else "Helvetica"
                text_width = pdfmetrics.stringWidth(max_text, font_name, 8.7) + 14
                widths.append(max(min_widths[col_idx], min(max_widths[col_idx], text_width)))

            total = sum(widths)
            if total < available_width:
                extra = available_width - total
                flex_indexes = [1, 3, 2]
                flex_total = sum(widths[i] for i in flex_indexes)
                for i in flex_indexes:
                    widths[i] += extra * (widths[i] / flex_total)
            elif total > available_width:
                ratio = available_width / total
                widths = [w * ratio for w in widths]
            return widths

        table_width = A4[0] - doc.leftMargin - doc.rightMargin
        retenus_table = Table(
            table_data,
            colWidths=_compute_col_widths(table_data, table_width),
            repeatRows=1,
            hAlign="LEFT",
        )
        retenus_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163C5B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8.8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFD"), colors.HexColor("#EEF3FA")]),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#1F2A37")),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8.4),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDE9")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                    ("TOPPADDING", (0, 1), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
                ]
            )
        )
        elements.append(retenus_table)

        doc.build(elements, onFirstPage=_draw_fixed_footer, onLaterPages=_draw_fixed_footer)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=candidats_retenus_aftec2026.pdf"
        return response

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
        by_day_map = {item["jour"]: item["total"] for item in by_day_qs}
        start_day = date.today() - timedelta(days=6)
        evolution_days = [start_day + timedelta(days=i) for i in range(7)]

        quiz_avg = QuizReponse.objects.aggregate(
            physique=Avg("score_physique"),
            mathematiques=Avg("score_mathematiques"),
            informatique=Avg("score_informatique"),
            ia=Avg("score_ia"),
            entrepreneuriat=Avg("score_entrepreneuriat"),
            divers=Avg("score_divers"),
        )

        top10 = StatutCandidat.objects.select_related("candidat").order_by("-score_global_selection")[:10]
        student_levels = Candidat.SECONDARY_LEVELS
        higher_levels = Candidat.HIGHER_AND_PRO_LEVELS

        student_quiz_ranking = (
            QuizReponse.objects.select_related("candidat")
            .filter(candidat__classe_niveau__in=student_levels)
            .order_by("-score_total", "candidat__date_inscription")
        )
        higher_quiz_ranking = (
            QuizReponse.objects.select_related("candidat")
            .filter(candidat__classe_niveau__in=higher_levels)
            .order_by("-score_total", "candidat__date_inscription")
        )

        def _serialize_quiz_ranking(rows, limit=20):
            sorted_rows = sorted(
                rows,
                key=lambda item: (
                    -int(item.score_total or 0),
                    int(item.quiz_elapsed_seconds) if int(item.quiz_elapsed_seconds or 0) > 0 else 999999,
                    item.candidat.date_inscription,
                ),
            )
            payload = []
            for index, row in enumerate(sorted_rows[:limit], start=1):
                payload.append(
                    {
                        "rank": index,
                        "nom": row.candidat.nom_complet,
                        "niveau": row.candidat.get_classe_niveau_display(),
                        "score": int(row.score_total or 0),
                        "temps": self._format_duration(row.quiz_elapsed_seconds),
                    }
                )
            return payload

        context["dashboard_data"] = {
            "total": total,
            "statuts": {
                "labels": ["En attente", "Retenu", "Liste d'attente", "Rejete"],
                "values": [
                    status_counts.get("EN_ATTENTE", 0),
                    status_counts.get("RETENU", 0),
                    status_counts.get("LISTE_ATTENTE", 0),
                    status_counts.get("REJETE", 0),
                ],
            },
            "sexe": {
                "labels": ["Masculin", "Feminin"],
                "values": [sexe_counts.get("M", 0), sexe_counts.get("F", 0)],
            },
            "classe": {
                "labels": [dict(Candidat.CLASSE_CHOICES).get(key, key) for key in classe_counts.keys()],
                "values": list(classe_counts.values()),
            },
            "evolution": {
                "labels": [d.isoformat() for d in evolution_days],
                "values": [by_day_map.get(d, 0) for d in evolution_days],
            },
            "quiz_avg": {
                "labels": ["Physique", "Mathematiques", "Informatique", "IA", "Entrepreneuriat", "Divers"],
                "values": [
                    round(float(quiz_avg.get("physique") or 0), 2),
                    round(float(quiz_avg.get("mathematiques") or 0), 2),
                    round(float(quiz_avg.get("informatique") or 0), 2),
                    round(float(quiz_avg.get("ia") or 0), 2),
                    round(float(quiz_avg.get("entrepreneuriat") or 0), 2),
                    round(float(quiz_avg.get("divers") or 0), 2),
                ],
            },
            "top10": [{"nom": item.candidat.nom_complet, "score": item.score_global_selection} for item in top10],
            "quiz_rankings": {
                "eleves": _serialize_quiz_ranking(student_quiz_ranking),
                "licence_pro": _serialize_quiz_ranking(higher_quiz_ranking),
            },
        }
        context["kcomat"] = settings.KCOMAT_INFO

        return context


aftec_admin_site = AFTECAdminSite(name="aftec_admin")
Documents._meta.verbose_name = "Document"
Documents._meta.verbose_name_plural = "Documents"
NotesAcademiques._meta.verbose_name = "Note academique"
NotesAcademiques._meta.verbose_name_plural = "Notes academiques"
aftec_admin_site.register(Candidat, CandidatAdmin)
aftec_admin_site.register(NotesAcademiques)
aftec_admin_site.register(Documents)
aftec_admin_site.register(Consentement)
aftec_admin_site.register(get_user_model(), UserAdmin)
aftec_admin_site.register(Group, GroupAdmin)


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
        except Exception as exc:
            obj.email_envoye = False
            obj.save(update_fields=["email_envoye"])
            self.message_user(
                request,
                f"Échec d'envoi email ({exc}). La case 'email envoyé' a été décochée automatiquement.",
                level=messages.WARNING,
            )

@admin.register(Challenge, site=aftec_admin_site)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("sequence_day", "title", "is_published", "published_at", "published_until", "updated_at")
    list_filter = ("is_published", "sequence_day")
    search_fields = ("title", "description")
    readonly_fields = ("published_at", "published_until", "created_at", "updated_at")
    ordering = ("sequence_day",)


@admin.register(ChallengeSubmission, site=aftec_admin_site)
class ChallengeSubmissionAdmin(admin.ModelAdmin):
    list_display = ("challenge", "candidat", "score", "elapsed_seconds", "started_at", "submitted_at")
    list_filter = ("challenge__sequence_day", "submitted_at")
    search_fields = ("candidat__nom", "candidat__prenom", "candidat__numero_dossier", "challenge__title")
    readonly_fields = ("started_at", "submitted_at", "elapsed_seconds", "created_at", "updated_at")
    autocomplete_fields = ("candidat", "challenge")


@admin.register(ChallengePortalSettings, site=aftec_admin_site)
class ChallengePortalSettingsAdmin(admin.ModelAdmin):
    list_display = ("is_enabled", "updated_at")
