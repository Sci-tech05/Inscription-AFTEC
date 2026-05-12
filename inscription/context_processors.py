from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import ChallengePortalSettings


def kcomat_info(request):
    challenge_nav_enabled = False
    try:
        challenge_nav_enabled = ChallengePortalSettings.get_solo().is_enabled
    except (OperationalError, ProgrammingError):
        challenge_nav_enabled = False
    return {
        "KCOMAT_INFO": settings.KCOMAT_INFO,
        "challenge_nav_enabled": challenge_nav_enabled,
    }
