from __future__ import annotations

from collections import defaultdict
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import InscriptionMultiStepForm
from .models import Candidat, Consentement, Documents, NotesAcademiques, QuizQuestion, QuizReponse, StatutCandidat


QUIZ_CATEGORY_ORDER = [
    "physique",
    "mathematiques",
    "informatique",
    "ia",
    "entrepreneuriat",
    "divers",
]

CATEGORY_LABELS = dict(QuizQuestion.CATEGORY_CHOICES)
CATEGORY_MAX_SCORES = {
    "physique": 10,
    "mathematiques": 10,
    "informatique": 5,
    "ia": 5,
    "entrepreneuriat": 5,
    "divers": 5,
}


def home(request):
    return render(request, "inscription/home.html")


def _build_quiz_tabs(form):
    grouped = defaultdict(list)
    for question in form.questions:
        field_name = f"question_{question.id}"
        grouped[question.categorie].append(
            {
                "question": question,
                "field": form[field_name],
            }
        )
    tabs = []
    for category in QUIZ_CATEGORY_ORDER:
        if not grouped.get(category):
            continue
        tabs.append(
            {
                "key": category,
                "label": CATEGORY_LABELS.get(category, category.title()),
                "items": grouped.get(category, []),
            }
        )
    return tabs


def _candidate_chart_data(candidat, quiz):
    categories = Candidat.quiz_categories_for_level(candidat.classe_niveau)
    score_fields = {
        "physique": "score_physique",
        "mathematiques": "score_mathematiques",
        "informatique": "score_informatique",
        "ia": "score_ia",
        "entrepreneuriat": "score_entrepreneuriat",
        "divers": "score_divers",
    }
    return {
        "labels": [CATEGORY_LABELS.get(category, category.title()) for category in categories],
        "scores": [getattr(quiz, score_fields[category], 0) for category in categories],
        "max_score": max((CATEGORY_MAX_SCORES.get(category, 0) for category in categories), default=0),
    }


@require_http_methods(["GET", "POST"])
def formulaire_inscription(request):
    if request.method == "POST":
        form = InscriptionMultiStepForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                candidat = Candidat.objects.create(
                    nom=form.cleaned_data["nom"],
                    prenom=form.cleaned_data["prenom"],
                    date_naissance=form.cleaned_data["date_naissance"],
                    sexe=form.cleaned_data["sexe"],
                    telephone=form.cleaned_data["telephone"],
                    email=form.cleaned_data["email"],
                    commune_residence=form.cleaned_data["commune_residence"],
                    etablissement=form.cleaned_data["etablissement"],
                    classe_niveau=form.cleaned_data["classe_niveau"],
                    filiere=form.cleaned_data["filiere"],
                )

                NotesAcademiques.objects.create(
                    candidat=candidat,
                    moyenne_generale_an1=form.cleaned_data["moyenne_generale_an1"],
                    moyenne_generale_an2=form.cleaned_data["moyenne_generale_an2"],
                    moyenne_maths_an1=form.cleaned_data["moyenne_maths_an1"],
                    moyenne_maths_an2=form.cleaned_data["moyenne_maths_an2"],
                    moyenne_physique_an1=form.cleaned_data["moyenne_physique_an1"],
                    moyenne_physique_an2=form.cleaned_data["moyenne_physique_an2"],
                    diplome_plus_eleve=form.cleaned_data.get("diplome_plus_eleve", ""),
                )

                Documents.objects.create(
                    candidat=candidat,
                    piece_identite=form.cleaned_data["piece_identite"],
                    bulletin_an1=form.cleaned_data.get("bulletin_an1"),
                    bulletin_an2=form.cleaned_data.get("bulletin_an2"),
                    lettre_motivation=form.cleaned_data["lettre_motivation"],
                    lettre_recommandation=form.cleaned_data.get("lettre_recommandation"),
                    attestation_diplome=form.cleaned_data.get("attestation_diplome"),
                    dernier_releve_notes=form.cleaned_data.get("dernier_releve_notes"),
                    autorisation_parentale=form.cleaned_data.get("autorisation_parentale"),
                )

                Consentement.objects.create(
                    candidat=candidat,
                    consent_donnees_personnelles=form.cleaned_data["consent_donnees_personnelles"],
                    consent_reglement=form.cleaned_data["consent_reglement"],
                    consent_selection=form.cleaned_data["consent_selection"],
                    consent_photos_videos=form.cleaned_data["consent_photos_videos"],
                    consent_autorisation_parentale_declaree=form.cleaned_data.get(
                        "consent_autorisation_parentale_declaree", False
                    ),
                    consent_engagement_presence=form.cleaned_data["consent_engagement_presence"],
                )

                quiz_scores = form.build_quiz_scores()
                QuizReponse.objects.create(candidat=candidat, **quiz_scores)
                StatutCandidat.objects.create(candidat=candidat)

            messages.success(request, "Votre candidature a été enregistrée avec succès.")
            return redirect("inscription:confirmation", candidat_id=candidat.id)

        messages.error(request, "Le formulaire contient des erreurs. Veuillez corriger les champs indiqués.")
    else:
        form = InscriptionMultiStepForm()

    context = {
        "form": form,
        "quiz_tabs": _build_quiz_tabs(form),
    }
    return render(request, "inscription/formulaire.html", context)


def confirmation(request, candidat_id):
    candidat = get_object_or_404(Candidat, pk=candidat_id)
    quiz = getattr(candidat, "quiz", None)
    notes = getattr(candidat, "notes", None)
    quiz_categories = Candidat.quiz_categories_for_level(candidat.classe_niveau)

    context = {
        "candidat": candidat,
        "quiz": quiz,
        "notes": notes,
        "quiz_total_max": sum(CATEGORY_MAX_SCORES.get(category, 0) for category in quiz_categories),
        "chart_data": _candidate_chart_data(candidat, quiz),
    }
    return render(request, "inscription/confirmation.html", context)


def confirmation_pdf(request, candidat_id):
    candidat = get_object_or_404(Candidat, pk=candidat_id)
    notes = getattr(candidat, "notes", None)
    documents = getattr(candidat, "documents", None)
    statut = getattr(candidat, "statut", None)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.0 * cm,
        bottomMargin=2.3 * cm,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="HeaderTitle",
            parent=styles["Heading1"],
            textColor=colors.white,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            alignment=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeaderSubtitle",
            parent=styles["Normal"],
            textColor=colors.HexColor("#E8F1FF"),
            fontSize=9.5,
            leading=12,
            alignment=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading3"],
            textColor=colors.HexColor("#132847"),
            fontName="Helvetica-Bold",
            fontSize=11.2,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["Normal"],
            textColor=colors.HexColor("#2B2B2B"),
            fontSize=9.6,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyMuted",
            parent=styles["Normal"],
            textColor=colors.HexColor("#5C6470"),
            fontSize=9.2,
            leading=11.5,
        )
    )

    elements = []
    footer_line_1 = (
        f"Organisation: {settings.KCOMAT_INFO['name']} | IFU: {settings.KCOMAT_INFO['ifu']} | "
        f"RCCM: {settings.KCOMAT_INFO['rccm']}"
    )
    footer_line_2 = (
        f"Contact officiel: {settings.KCOMAT_INFO['phone']} | {settings.KCOMAT_INFO['email']} | "
        f"{settings.KCOMAT_INFO['address']}"
    )
    footer_line_3 = f"Site: {settings.KCOMAT_INFO['site']}"

    def _draw_fixed_footer(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#5C6470"))
        canvas.setFont("Helvetica", 9.2)
        center_x = A4[0] / 2
        canvas.drawCentredString(center_x, 1.45 * cm, footer_line_1)
        canvas.drawCentredString(center_x, 1.05 * cm, footer_line_2)
        canvas.setFont("Helvetica-Bold", 9.2)
        canvas.drawCentredString(center_x, 0.65 * cm, footer_line_3)
        canvas.restoreState()

    def _fit_logo(path, max_width_cm, max_height_cm):
        if not path.exists():
            return ""
        logo = RLImage(str(path))
        max_w = max_width_cm * cm
        max_h = max_height_cm * cm
        ratio = min(max_w / float(logo.imageWidth), max_h / float(logo.imageHeight))
        logo.drawWidth = float(logo.imageWidth) * ratio
        logo.drawHeight = float(logo.imageHeight) * ratio
        logo.hAlign = "CENTER"
        return logo

    logo_aftec = settings.BASE_DIR / "static" / "img" / "logo-aftec.png"
    logo_kcomat = settings.BASE_DIR / "static" / "img" / "logo-kcomat.jpeg"
    left_logo = _fit_logo(logo_aftec, 3.8, 1.6)
    right_logo = _fit_logo(logo_kcomat, 4.8, 1.6)
    header_text = [
        Paragraph("FORMULAIRE OFFICIEL", styles["HeaderTitle"]),
        Paragraph("D'INSCRIPTION", styles["HeaderTitle"]),
        Paragraph("AFTEC 2026 | Session du 03 au 21 Août 2026 | Pobè, Bénin", styles["HeaderSubtitle"]),
        Paragraph(f"Numéro de dossier: <b>{candidat.numero_dossier}</b>", styles["HeaderSubtitle"]),
    ]
    available_width = A4[0] - doc.leftMargin - doc.rightMargin
    side_col_width = 4.1 * cm
    header_table = Table(
        [[left_logo, header_text, right_logo]],
        colWidths=[side_col_width, available_width - (2 * side_col_width), side_col_width],
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
    elements.append(Spacer(1, 0.34 * cm))

    elements.append(Paragraph("Informations du candidat", styles["SectionTitle"]))
    profil_data = [
        ["Nom complet", candidat.nom_complet],
        ["Email", candidat.email],
        ["Téléphone", candidat.telephone],
        ["Date de naissance", candidat.date_naissance.strftime("%d/%m/%Y")],
        ["Sexe", candidat.get_sexe_display()],
        ["Commune de résidence", candidat.commune_residence],
        ["Établissement", candidat.etablissement],
        ["Classe / Niveau", candidat.get_classe_niveau_display()],
        ["Filière", candidat.filiere],
        ["Date d'inscription", candidat.date_inscription.strftime("%d/%m/%Y à %H:%M")],
    ]
    profile_table = Table(profil_data, colWidths=[5.7 * cm, 11.1 * cm], hAlign="LEFT")
    profile_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFD")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F8FAFD"), colors.HexColor("#EEF3FA")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDE9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#162742")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1F2A37")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(profile_table)
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(Paragraph("Parcours académique", styles["SectionTitle"]))

    def _note_or_dash(value):
        return f"{value}/20" if value is not None else "-"

    is_professional = candidat.classe_niveau == "AUTRE"
    if is_professional:
        notes_data = [
            ["Diplôme le plus élevé", getattr(notes, "diplome_plus_eleve", "") or "-"],
        ]
    else:
        notes_data = [
            ["Moyenne générale Année passée", _note_or_dash(getattr(notes, "moyenne_generale_an1", None))],
            ["Moyenne générale S1 Année actuel", _note_or_dash(getattr(notes, "moyenne_generale_an2", None))],
            ["Moyenne maths Semestre 1", _note_or_dash(getattr(notes, "moyenne_maths_an1", None))],
            ["Moyenne maths Semestre 2", _note_or_dash(getattr(notes, "moyenne_maths_an2", None))],
            ["Moyenne physique Semestre 1", _note_or_dash(getattr(notes, "moyenne_physique_an1", None))],
            ["Moyenne physique Semestre 2", _note_or_dash(getattr(notes, "moyenne_physique_an2", None))],
        ]
    notes_table = Table(notes_data, colWidths=[9.5 * cm, 7.3 * cm], hAlign="LEFT")
    notes_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F9FE")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDE9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#162742")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#223143")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(notes_table)
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(Paragraph("Documents joints", styles["SectionTitle"]))

    def _doc_or_dash(file_field):
        if not file_field:
            return "-"
        return file_field.name.split("/")[-1]

    documents_data = [["Pièce d'identité", _doc_or_dash(getattr(documents, "piece_identite", None))]]
    if is_professional:
        documents_data.extend(
            [
                ["Attestation du diplôme", _doc_or_dash(getattr(documents, "attestation_diplome", None))],
                ["Dernier relevé de notes", _doc_or_dash(getattr(documents, "dernier_releve_notes", None))],
            ]
        )
    else:
        documents_data.extend(
            [
                ["Bulletin Année passée", _doc_or_dash(getattr(documents, "bulletin_an1", None))],
                ["Bulletin S1 année actuelle", _doc_or_dash(getattr(documents, "bulletin_an2", None))],
            ]
        )
    documents_data.append(["Lettre recommandation (facultative)", _doc_or_dash(getattr(documents, "lettre_recommandation", None))])
    if candidat.est_mineur:
        documents_data.append(
            ["Autorisation parentale", _doc_or_dash(getattr(documents, "autorisation_parentale", None))]
        )

    documents_table = Table(documents_data, colWidths=[7.4 * cm, 9.4 * cm], hAlign="LEFT")
    documents_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F9FE")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDE9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#162742")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#223143")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(documents_table)
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(Paragraph("Situation du dossier", styles["SectionTitle"]))
    status_text = statut.get_statut_display() if statut else "En attente"
    date_decision = statut.date_decision.strftime("%d/%m/%Y") if statut else "-"
    dossier_table = Table(
        [
            ["Statut actuel du dossier", status_text],
            ["Dernière mise à jour", date_decision],
            ["Référence du programme", "AFTEC 2026 - Formation Technologique Intensive"],
        ],
        colWidths=[6.2 * cm, 10.6 * cm],
        hAlign="LEFT",
    )
    dossier_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFD")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDE9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#162742")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#223143")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(dossier_table)
    elements.append(Spacer(1, 0.45 * cm))

    elements.append(
        Paragraph(
            "Ce document confirme l'enregistrement officiel de votre candidature AFTEC 2026. "
            "Conservez-le pour tout suivi administratif.",
            styles["BodySmall"],
        )
    )
    doc.build(elements, onFirstPage=_draw_fixed_footer, onLaterPages=_draw_fixed_footer)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="formulaire_inscription_{candidat.numero_dossier}.pdf"'
    return response


def quiz_info(request):
    form = InscriptionMultiStepForm()
    return render(request, "inscription/quiz.html", {"quiz_tabs": _build_quiz_tabs(form)})


