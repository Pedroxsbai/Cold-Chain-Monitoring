# WSGI file for PythonAnywhere.
# Copy this content into the WSGI file linked in the "Web" tab
# (/var/www/<username>_pythonanywhere_com_wsgi.py) and replace USERNAME.
# The settings read backend/.env themselves: nothing else to configure here.

import os
import sys

BACKEND = "/home/USERNAME/Cold-Chain-Monitoring/backend"
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
