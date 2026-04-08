import os
import sys

# Add your project directory to the sys.path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.append(project_home)

# Set the environment variables for Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'core_project.settings_prod'

# Handle PyMySQL compatibility (Spoof mysqlclient version)
import pymysql
pymysql.version_info = (2, 2, 4, "final", 0)
pymysql.install_as_MySQLdb()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
