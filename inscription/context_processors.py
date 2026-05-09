from django.conf import settings


def kcomat_info(request):
    return {'KCOMAT_INFO': settings.KCOMAT_INFO}
