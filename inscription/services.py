from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def send_decision_email(candidat, statut_code: str, commentaire: str = ""):
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "")
    is_smtp_backend = backend.endswith("smtp.EmailBackend")
    if is_smtp_backend and not str(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "").strip():
        raise RuntimeError(
            "Configuration email incomplète: EMAIL_HOST_PASSWORD est vide. "
            "Renseignez le mot de passe d'application SMTP dans les variables d'environnement."
        )

    if statut_code == "RETENU":
        subject = "AFTEC 2026 - Candidature retenue"
        status_label = "retenue"
        intro = (
            "Nous avons le plaisir de vous informer que votre candidature a été retenue "
            "pour AFTEC 2026."
        )
    elif statut_code == "REJETE":
        subject = "AFTEC 2026 - Résultat de candidature"
        status_label = "non retenue"
        intro = (
            "Après étude de votre dossier, votre candidature n'a pas été retenue pour cette édition."
        )
    elif statut_code == "LISTE_ATTENTE":
        subject = "AFTEC 2026 - Liste d'attente"
        status_label = "placée en liste d'attente"
        intro = "Votre candidature est actuellement placée en liste d'attente."
    else:
        subject = "AFTEC 2026 - Mise à jour de candidature"
        status_label = "mise à jour"
        intro = "Le statut de votre candidature a été mis à jour."

    plain_body = (
        f"Bonjour {candidat.prenom} {candidat.nom},\n\n"
        f"{intro}\n"
        f"Numéro de dossier: {candidat.numero_dossier}\n"
        f"Statut: {status_label}\n\n"
        f"{('Commentaire du jury: ' + commentaire + '\n\n') if commentaire else ''}"
        f"Pour toute information:\n"
        f"{settings.KCOMAT_INFO['name']}\n"
        f"Email: {settings.KCOMAT_INFO['email']}\n"
        f"Téléphone: {settings.KCOMAT_INFO['phone']}\n"
        f"Site: {settings.KCOMAT_INFO['site']}\n"
    )

    html_body = f"""
    <p>Bonjour <strong>{candidat.prenom} {candidat.nom}</strong>,</p>
    <p>{intro}</p>
    <p>
      <strong>Numéro de dossier:</strong> {candidat.numero_dossier}<br>
      <strong>Statut:</strong> {status_label}
    </p>
    {f'<p><strong>Commentaire du jury:</strong> {commentaire}</p>' if commentaire else ''}
    <hr>
    <p>
      <strong>{settings.KCOMAT_INFO['name']}</strong><br>
      Email: {settings.KCOMAT_INFO['email']}<br>
      Téléphone: {settings.KCOMAT_INFO['phone']}<br>
      Site: <a href="{settings.KCOMAT_INFO['site']}">{settings.KCOMAT_INFO['site']}</a>
    </p>
    """

    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[candidat.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
