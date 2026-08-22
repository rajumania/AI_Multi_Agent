import sys
import os

venv_site_packages = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "Lib", "site-packages"))
if venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)

import check_env
