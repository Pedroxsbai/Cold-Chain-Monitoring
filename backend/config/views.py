from django.conf import settings
from django.http import HttpResponse


def frontend(request):
    """index.html of the React build, for every client-side route (/, /incidents/12, ...).

    The build's other files (/assets/*, /favicon.svg) are served by WhiteNoise.
    """
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return HttpResponse(
            "Interface non installée : construisez le frontend (npm run build) "
            "puis copiez frontend/dist sur le serveur.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    response = HttpResponse(index.read_bytes(), content_type="text/html; charset=utf-8")
    # index.html points to hashed assets: never cache it, so a new build shows at once.
    response["Cache-Control"] = "no-cache"
    return response
