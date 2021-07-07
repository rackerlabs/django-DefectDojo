# Django settings for DefectDojo
import os
from datetime import timedelta
from celery.schedules import crontab
from dojo import __version__
import environ


root = environ.Path(__file__) - 3  # Three folders back

# reference: https://pypi.org/project/django-environ/
env = environ.Env(
    # Set casting and default values
    DD_SITE_URL=(str, 'http://localhost:8080'),
    DD_DEBUG=(bool, False),
    DD_TEMPLATE_DEBUG=(bool, False),
    DD_LOG_LEVEL=(str, ''),
    DD_DJANGO_METRICS_ENABLED=(bool, False),
    DD_LOGIN_REDIRECT_URL=(str, '/'),
    DD_LOGIN_URL=(str, '/login'),
    DD_DJANGO_ADMIN_ENABLED=(bool, True),
    DD_SESSION_COOKIE_HTTPONLY=(bool, True),
    DD_CSRF_COOKIE_HTTPONLY=(bool, True),
    DD_SECURE_SSL_REDIRECT=(bool, False),
    DD_SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, False),
    DD_SECURE_HSTS_SECONDS=(int, 31536000),  # One year expiration
    DD_SESSION_COOKIE_SECURE=(bool, False),
    DD_SESSION_EXPIRE_AT_BROWSER_CLOSE=(bool, False),
    DD_SESSION_COOKIE_AGE=(int, 1209600),  # 14 days
    DD_CSRF_COOKIE_SECURE=(bool, False),
    DD_SECURE_BROWSER_XSS_FILTER=(bool, True),
    DD_SECURE_CONTENT_TYPE_NOSNIFF=(bool, True),
    DD_TIME_ZONE=(str, 'UTC'),
    DD_LANG=(str, 'en-us'),
    DD_TEAM_NAME=(str, 'Security Team'),
    DD_ADMINS=(str, 'DefectDojo:dojo@localhost,Admin:admin@localhost'),
    DD_WHITENOISE=(bool, False),
    DD_TRACK_MIGRATIONS=(bool, False),
    DD_SECURE_PROXY_SSL_HEADER=(bool, False),
    DD_TEST_RUNNER=(str, 'django.test.runner.DiscoverRunner'),
    DD_URL_PREFIX=(str, ''),
    DD_ROOT=(str, root('dojo')),
    DD_LANGUAGE_CODE=(str, 'en-us'),
    DD_SITE_ID=(int, 1),
    DD_USE_I18N=(bool, True),
    DD_USE_L10N=(bool, True),
    DD_USE_TZ=(bool, True),
    DD_MEDIA_URL=(str, '/media/'),
    DD_MEDIA_ROOT=(str, root('media')),
    DD_STATIC_URL=(str, '/static/'),
    DD_STATIC_ROOT=(str, root('static')),
    DD_CELERY_BROKER_URL=(str, ''),
    DD_CELERY_BROKER_SCHEME=(str, 'sqla+sqlite'),
    DD_CELERY_BROKER_USER=(str, ''),
    DD_CELERY_BROKER_PASSWORD=(str, ''),
    DD_CELERY_BROKER_HOST=(str, ''),
    DD_CELERY_BROKER_PORT=(int, -1),
    DD_CELERY_BROKER_PATH=(str, '/dojo.celerydb.sqlite'),
    DD_CELERY_BROKER_PARAMS=(str, ''),
    DD_CELERY_TASK_IGNORE_RESULT=(bool, True),
    DD_CELERY_RESULT_BACKEND=(str, 'django-db'),
    DD_CELERY_RESULT_EXPIRES=(int, 86400),
    DD_CELERY_BEAT_SCHEDULE_FILENAME=(str, root('dojo.celery.beat.db')),
    DD_CELERY_TASK_SERIALIZER=(str, 'pickle'),
    DD_CELERY_PASS_MODEL_BY_ID=(str, True),
    DD_FOOTER_VERSION=(str, ''),
    # models should be passed to celery by ID, default is False (for now)
    DD_FORCE_LOWERCASE_TAGS=(bool, True),
    DD_MAX_TAG_LENGTH=(int, 25),
    DD_DATABASE_ENGINE=(str, 'django.db.backends.mysql'),
    DD_DATABASE_HOST=(str, 'mysql'),
    DD_DATABASE_NAME=(str, 'defectdojo'),
    # default django database name for testing is test_<dbname>
    DD_TEST_DATABASE_NAME=(str, 'test_defectdojo'),
    DD_DATABASE_PASSWORD=(str, 'defectdojo'),
    DD_DATABASE_PORT=(int, 3306),
    DD_DATABASE_USER=(str, 'defectdojo'),
    DD_SECRET_KEY=(str, ''),
    DD_CREDENTIAL_AES_256_KEY=(str, '.'),
    DD_DATA_UPLOAD_MAX_MEMORY_SIZE=(int, 8388608),  # Max post size set to 8mb
    DD_SOCIAL_AUTH_SHOW_LOGIN_FORM=(bool, True),  # do we show user/pass input
    DD_SOCIAL_LOGIN_AUTO_REDIRECT=(bool, False),  # auto-redirect if there is only one social login method
    DD_SOCIAL_AUTH_TRAILING_SLASH=(bool, True),
    DD_SOCIAL_AUTH_AUTH0_OAUTH2_ENABLED=(bool, False),
    DD_SOCIAL_AUTH_AUTH0_KEY=(str, ''),
    DD_SOCIAL_AUTH_AUTH0_SECRET=(str, ''),
    DD_SOCIAL_AUTH_AUTH0_DOMAIN=(str, ''),
    DD_SOCIAL_AUTH_AUTH0_SCOPE=(list, ['openid', 'profile', 'email']),
    DD_SOCIAL_AUTH_GOOGLE_OAUTH2_ENABLED=(bool, False),
    DD_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=(str, ''),
    DD_SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET=(str, ''),
    DD_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS=(list, ['']),
    DD_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_EMAILS=(list, ['']),
    DD_SOCIAL_AUTH_OKTA_OAUTH2_ENABLED=(bool, False),
    DD_SOCIAL_AUTH_OKTA_OAUTH2_KEY=(str, ''),
    DD_SOCIAL_AUTH_OKTA_OAUTH2_SECRET=(str, ''),
    DD_SOCIAL_AUTH_OKTA_OAUTH2_API_URL=(str, 'https://{your-org-url}/oauth2/default'),
    DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_ENABLED=(bool, False),
    DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY=(str, ''),
    DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_SECRET=(str, ''),
    DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID=(str, ''),
    DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_RESOURCE=(str, 'https://graph.microsoft.com/'),
    DD_SOCIAL_AUTH_GITLAB_OAUTH2_ENABLED=(bool, False),
    DD_SOCIAL_AUTH_GITLAB_PROJECT_AUTO_IMPORT=(bool, False),
    DD_SOCIAL_AUTH_GITLAB_PROJECT_MIN_ACCESS_LEVEL=(int, 20),
    DD_SOCIAL_AUTH_GITLAB_KEY=(str, ''),
    DD_SOCIAL_AUTH_GITLAB_SECRET=(str, ''),
    DD_SOCIAL_AUTH_GITLAB_API_URL=(str, 'https://gitlab.com'),
    DD_SOCIAL_AUTH_GITLAB_SCOPE=(list, ['api', 'read_user', 'openid', 'profile', 'email']),
    DD_SAML2_ENABLED=(bool, False),
    # Optional: display the idp SAML Logout URL in DefectDojo
    DD_SAML2_LOGOUT_URL=(str, ''),
    # Metadata is required for SAML, choose either remote url or local file path
    DD_SAML2_METADATA_AUTO_CONF_URL=(str, ''),
    DD_SAML2_METADATA_LOCAL_FILE_PATH=(str, ''),  # ex. '/public/share/idp_metadata.xml'
    # Optional, default is SITE_URL + /saml2/metadata/
    DD_SAML2_ENTITY_ID=(str, ''),
    # Allow to create user that are not already in the Django database
    DD_SAML2_CREATE_USER=(bool, False),
    DD_SAML2_ATTRIBUTES_MAP=(dict, {
        # Change Email/UserName/FirstName/LastName to corresponding SAML2 userprofile attributes.
        'Email': ('email', ),
        'UserName': ('username', ),
        'Firstname': ('first_name', ),
        'Lastname': ('last_name', )
    }),
    # merging findings doesn't always work well with dedupe and reimport etc.
    # disable it if you see any issues (and report them on github)
    DD_DISABLE_FINDING_MERGE=(bool, False),
    # Set to True if you want to allow authorized users to make changes to findings or delete them
    DD_AUTHORIZED_USERS_ALLOW_CHANGE=(bool, False),
    DD_AUTHORIZED_USERS_ALLOW_DELETE=(bool, False),
    # Set to True if you want to allow authorized users staff access only on specific products
    # This will only apply to users with 'active' status
    DD_AUTHORIZED_USERS_ALLOW_STAFF=(bool, False),
    # SLA Notifications via alerts and JIRA comments
    # enable either DD_SLA_NOTIFY_ACTIVE or DD_SLA_NOTIFY_ACTIVE_VERIFIED_ONLY to enable the feature
    DD_SLA_NOTIFY_ACTIVE=(bool, False),
    DD_SLA_NOTIFY_ACTIVE_VERIFIED_ONLY=(bool, False),
    # finetuning settings for when enabled
    DD_SLA_NOTIFY_WITH_JIRA_ONLY=(bool, False),
    DD_SLA_NOTIFY_PRE_BREACH=(int, 3),
    DD_SLA_NOTIFY_POST_BREACH=(int, 7),
    # maximum number of result in search as search can be an expensive operation
    DD_SEARCH_MAX_RESULTS=(int, 100),
    DD_SIMILAR_FINDINGS_MAX_RESULTS=(int, 25),
    DD_MAX_AUTOCOMPLETE_WORDS=(int, 20000),
    DD_JIRA_SSL_VERIFY=(bool, True),
    # if you want to keep logging to the console but in json format, change this here to 'json_console'
    DD_LOGGING_HANDLER=(str, 'console'),
    DD_ALERT_REFRESH=(bool, True),
    DD_DISABLE_ALERT_COUNTER=(bool, False),
    # to disable deleting alerts per user set value to -1
    DD_MAX_ALERTS_PER_USER=(int, 999),
    DD_TAG_PREFETCHING=(bool, True),
    DD_QUALYS_WAS_WEAKNESS_IS_VULN=(bool, False),
    # when enabled in sytem settings,  every minute a job run to delete excess duplicates
    # we limit the amount of duplicates that can be deleted in a single run of that job
    # to prevent overlapping runs of that job from occurrring
    DD_DUPE_DELETE_MAX_PER_RUN=(int, 200),
    # APIv1 is depreacted and will be removed at 2021-06-30
    DD_LEGACY_API_V1_ENABLE=(bool, False),
    # when enabled 'mitigated date' and 'mitigated by' of a finding become editable
    DD_EDITABLE_MITIGATED_DATA=(bool, False),
    # new experimental feature that tracks history across multiple reimports for the same test
    DD_TRACK_IMPORT_HISTORY=(bool, False),

    # Feature toggle for new authorization, which is incomplete at the moment.
    # Don't set it to True for productive environments!
    DD_FEATURE_AUTHORIZATION_V2=(bool, True),
    # When enabled, staff users have full access to all product types and products
    DD_AUTHORIZATION_STAFF_OVERRIDE=(bool, False),

    DD_FEATURE_FINDING_GROUPS=(bool, False),
    DD_JIRA_TEMPLATE_ROOT=(str, 'dojo/templates/issue-trackers'),
    DD_TEMPLATE_DIR_PREFIX=(str, 'dojo/templates/'),

    # Initial behaviour in Defect Dojo was to delete all duplicates when an original was deleted
    # New behaviour is to leave the duplicates in place, but set the oldest of duplicates as new original
    # Set to True to revert to the old behaviour where all duplicates are deleted
    DD_DUPLICATE_CLUSTER_CASCADE_DELETE=(str, False),
    # Enable Rate Limiting for the login page
    DD_RATE_LIMITER_ENABLED=(bool, False),
    # Examples include 5/m 100/h and more https://django-ratelimit.readthedocs.io/en/stable/rates.html#simple-rates
    DD_RATE_LIMITER_RATE=(str, '5/m'),
    # Block the requests after rate limit is exceeded
    DD_RATE_LIMITER_BLOCK=(bool, False),
    # Forces the user to change password on next login.
    DD_RATE_LIMITER_ACCOUNT_LOCKOUT=(bool, False),
)


def generate_url(scheme, double_slashes, user, password, host, port, path, params):
    result_list = []
    result_list.append(scheme)
    result_list.append(':')
    if double_slashes:
        result_list.append('//')
    result_list.append(user)
    if len(password) > 0:
        result_list.append(':')
        result_list.append(password)
    if len(user) > 0 or len(password) > 0:
        result_list.append('@')
    result_list.append(host)
    if port >= 0:
        result_list.append(':')
        result_list.append(str(port))
    if len(path) > 0 and path[0] != '/':
        result_list.append('/')
    result_list.append(path)
    if len(params) > 0 and params[0] != '?':
        result_list.append('?')
    result_list.append(params)
    return ''.join(result_list)


# Read .env file as default or from the command line, DD_ENV_PATH
if os.path.isfile(root('dojo/settings/.env.prod')) or 'DD_ENV_PATH' in os.environ:
    env.read_env(root('dojo/settings/' + env.str('DD_ENV_PATH', '.env.prod')))

# ------------------------------------------------------------------------------
# GENERAL
# ------------------------------------------------------------------------------

# False if not in os.environ
DEBUG = env('DD_DEBUG')
TEMPLATE_DEBUG = env('DD_TEMPLATE_DEBUG')

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/2.0/ref/settings/#allowed-hosts
SITE_URL = env('DD_SITE_URL')
ALLOWED_HOSTS = tuple(env.list('DD_ALLOWED_HOSTS', default=['localhost', '127.0.0.1']))

# Raises django's ImproperlyConfigured exception if SECRET_KEY not in os.environ
SECRET_KEY = env('DD_SECRET_KEY')

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = env('DD_TIME_ZONE')

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = env('DD_LANGUAGE_CODE')

SITE_ID = env('DD_SITE_ID')

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = env('DD_USE_I18N')

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = env('DD_USE_L10N')

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = env('DD_USE_TZ')

TEST_RUNNER = env('DD_TEST_RUNNER')

ALERT_REFRESH = env('DD_ALERT_REFRESH')
DISABLE_ALERT_COUNTER = env("DD_DISABLE_ALERT_COUNTER")
MAX_ALERTS_PER_USER = env("DD_MAX_ALERTS_PER_USER")

TAG_PREFETCHING = env('DD_TAG_PREFETCHING')

# ------------------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------------------

# Parse database connection url strings like psql://user:pass@127.0.0.1:8458/db
if os.getenv('DD_DATABASE_URL') is not None:
    DATABASES = {
        'default': env.db('DD_DATABASE_URL')
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': env('DD_DATABASE_ENGINE'),
            'NAME': env('DD_DATABASE_NAME'),
            'TEST': {
                'NAME': env('DD_TEST_DATABASE_NAME'),
            },
            'USER': env('DD_DATABASE_USER'),
            'PASSWORD': env('DD_DATABASE_PASSWORD'),
            'HOST': env('DD_DATABASE_HOST'),
            'PORT': env('DD_DATABASE_PORT'),
        }
    }

# Track migrations through source control rather than making migrations locally
if env('DD_TRACK_MIGRATIONS'):
    MIGRATION_MODULES = {'dojo': 'dojo.db_migrations'}

# ------------------------------------------------------------------------------
# MEDIA
# ------------------------------------------------------------------------------

DOJO_ROOT = env('DD_ROOT')

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = env('DD_MEDIA_ROOT')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = env('DD_MEDIA_URL')

# ------------------------------------------------------------------------------
# STATIC
# ------------------------------------------------------------------------------

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = env('DD_STATIC_ROOT')

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = env('DD_STATIC_URL')

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(os.path.dirname(DOJO_ROOT), 'components', 'node_modules'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

FILE_UPLOAD_HANDLERS = (
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
)

DATA_UPLOAD_MAX_MEMORY_SIZE = env('DD_DATA_UPLOAD_MAX_MEMORY_SIZE')

# ------------------------------------------------------------------------------
# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf

# AUTHENTICATION_BACKENDS = [
# 'axes.backends.AxesModelBackend',
# ]

ROOT_URLCONF = 'dojo.urls'

# Python dotted path to the WSGI application used by Django's runserver.
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = 'dojo.wsgi.application'

URL_PREFIX = env('DD_URL_PREFIX')

# ------------------------------------------------------------------------------
# AUTHENTICATION
# ------------------------------------------------------------------------------

LOGIN_REDIRECT_URL = env('DD_LOGIN_REDIRECT_URL')
LOGIN_URL = env('DD_LOGIN_URL')

# These are the individidual modules supported by social-auth
AUTHENTICATION_BACKENDS = (
    'social_core.backends.auth0.Auth0OAuth2',
    'social_core.backends.google.GoogleOAuth2',
    'dojo.okta.OktaOAuth2',
    'social_core.backends.azuread_tenant.AzureADTenantOAuth2',
    'social_core.backends.gitlab.GitLabOAuth2',
    'django.contrib.auth.backends.RemoteUserBackend',
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'dojo.pipeline.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.social_auth.associate_by_email',
    'social_core.pipeline.user.create_user',
    'dojo.pipeline.modify_permissions',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'dojo.pipeline.update_product_access',
)

CLASSIC_AUTH_ENABLED = True
# Showing login form (form is not needed for external auth: OKTA, Google Auth, etc.)
SHOW_LOGIN_FORM = env('DD_SOCIAL_AUTH_SHOW_LOGIN_FORM')
SOCIAL_LOGIN_AUTO_REDIRECT = env('DD_SOCIAL_LOGIN_AUTO_REDIRECT')

SOCIAL_AUTH_STRATEGY = 'social_django.strategy.DjangoStrategy'
SOCIAL_AUTH_STORAGE = 'social_django.models.DjangoStorage'
SOCIAL_AUTH_ADMIN_USER_SEARCH_FIELDS = ['username', 'first_name', 'last_name', 'email']
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True

GOOGLE_OAUTH_ENABLED = env('DD_SOCIAL_AUTH_GOOGLE_OAUTH2_ENABLED')
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env('DD_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env('DD_SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET')
SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS = env('DD_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS')
SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_EMAILS = env('DD_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_EMAILS')
SOCIAL_AUTH_LOGIN_ERROR_URL = '/login'
SOCIAL_AUTH_BACKEND_ERROR_URL = '/login'

OKTA_OAUTH_ENABLED = env('DD_SOCIAL_AUTH_OKTA_OAUTH2_ENABLED')
SOCIAL_AUTH_OKTA_OAUTH2_KEY = env('DD_SOCIAL_AUTH_OKTA_OAUTH2_KEY')
SOCIAL_AUTH_OKTA_OAUTH2_SECRET = env('DD_SOCIAL_AUTH_OKTA_OAUTH2_SECRET')
SOCIAL_AUTH_OKTA_OAUTH2_API_URL = env('DD_SOCIAL_AUTH_OKTA_OAUTH2_API_URL')

AZUREAD_TENANT_OAUTH2_ENABLED = env('DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_ENABLED')
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY = env('DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY')
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_SECRET = env('DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_SECRET')
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID = env('DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID')
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_RESOURCE = env('DD_SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_RESOURCE')

GITLAB_OAUTH2_ENABLED = env('DD_SOCIAL_AUTH_GITLAB_OAUTH2_ENABLED')
GITLAB_PROJECT_AUTO_IMPORT = env('DD_SOCIAL_AUTH_GITLAB_PROJECT_AUTO_IMPORT')
GITLAB_PROJECT_MIN_ACCESS_LEVEL = env('DD_SOCIAL_AUTH_GITLAB_PROJECT_MIN_ACCESS_LEVEL')
SOCIAL_AUTH_GITLAB_KEY = env('DD_SOCIAL_AUTH_GITLAB_KEY')
SOCIAL_AUTH_GITLAB_SECRET = env('DD_SOCIAL_AUTH_GITLAB_SECRET')
SOCIAL_AUTH_GITLAB_API_URL = env('DD_SOCIAL_AUTH_GITLAB_API_URL')
SOCIAL_AUTH_GITLAB_SCOPE = env('DD_SOCIAL_AUTH_GITLAB_SCOPE')

AUTH0_OAUTH2_ENABLED = env('DD_SOCIAL_AUTH_AUTH0_OAUTH2_ENABLED')
SOCIAL_AUTH_AUTH0_KEY = env('DD_SOCIAL_AUTH_AUTH0_KEY')
SOCIAL_AUTH_AUTH0_SECRET = env('DD_SOCIAL_AUTH_AUTH0_SECRET')
SOCIAL_AUTH_AUTH0_DOMAIN = env('DD_SOCIAL_AUTH_AUTH0_DOMAIN')
SOCIAL_AUTH_AUTH0_SCOPE = env('DD_SOCIAL_AUTH_AUTH0_SCOPE')
SOCIAL_AUTH_TRAILING_SLASH = env('DD_SOCIAL_AUTH_TRAILING_SLASH')

AUTHORIZED_USERS_ALLOW_CHANGE = env('DD_AUTHORIZED_USERS_ALLOW_CHANGE')
AUTHORIZED_USERS_ALLOW_DELETE = env('DD_AUTHORIZED_USERS_ALLOW_DELETE')
AUTHORIZED_USERS_ALLOW_STAFF = env('DD_AUTHORIZED_USERS_ALLOW_STAFF')

# Setting SLA_NOTIFY_ACTIVE and SLA_NOTIFY_ACTIVE_VERIFIED to False will disable the feature
# If you import thousands of Active findings through your pipeline everyday,
# and make the choice of enabling SLA notifications for non-verified findings,
# be mindful of performance.
SLA_NOTIFY_ACTIVE = env('DD_SLA_NOTIFY_ACTIVE')  # this will include 'verified' findings as well as non-verified.
SLA_NOTIFY_ACTIVE_VERIFIED_ONLY = env('DD_SLA_NOTIFY_ACTIVE_VERIFIED_ONLY')
SLA_NOTIFY_WITH_JIRA_ONLY = env('DD_SLA_NOTIFY_WITH_JIRA_ONLY')  # Based on the 2 above, but only with a JIRA link
SLA_NOTIFY_PRE_BREACH = env('DD_SLA_NOTIFY_PRE_BREACH')  # in days, notify between dayofbreach minus this number until dayofbreach
SLA_NOTIFY_POST_BREACH = env('DD_SLA_NOTIFY_POST_BREACH')  # in days, skip notifications for findings that go past dayofbreach plus this number

SEARCH_MAX_RESULTS = env('DD_SEARCH_MAX_RESULTS')
SIMILAR_FINDINGS_MAX_RESULTS = env('DD_SIMILAR_FINDINGS_MAX_RESULTS')
MAX_AUTOCOMPLETE_WORDS = env('DD_MAX_AUTOCOMPLETE_WORDS')

LOGIN_EXEMPT_URLS = (
    r'^%sstatic/' % URL_PREFIX,
    r'^%swebhook/([\w-]+)$' % URL_PREFIX,
    r'^%swebhook/' % URL_PREFIX,
    r'^%sjira/webhook/([\w-]+)$' % URL_PREFIX,
    r'^%sjira/webhook/' % URL_PREFIX,
    r'^%sreports/cover$' % URL_PREFIX,
    r'^%sfinding/image/(?P<token>[^/]+)$' % URL_PREFIX,
    r'^%sapi/v2/' % URL_PREFIX,
    r'complete/',
    r'empty_questionnaire/([\d]+)/answer'
)

LEGACY_API_V1_ENABLE = env('DD_LEGACY_API_V1_ENABLE')

# https://django-ratelimit.readthedocs.io/en/stable/index.html
RATE_LIMITER_ENABLED = env('DD_RATE_LIMITER_ENABLED')
RATE_LIMITER_RATE = env('DD_RATE_LIMITER_RATE')  # Examples include 5/m 100/h and more https://django-ratelimit.readthedocs.io/en/stable/rates.html#simple-rates
RATE_LIMITER_BLOCK = env('DD_RATE_LIMITER_BLOCK')  # Block the requests after rate limit is exceeded
RATE_LIMITER_ACCOUNT_LOCKOUT = env('DD_RATE_LIMITER_ACCOUNT_LOCKOUT')  # Forces the user to change password on next login.

# ------------------------------------------------------------------------------
# SECURITY DIRECTIVES
# ------------------------------------------------------------------------------

# If True, the SecurityMiddleware redirects all non-HTTPS requests to HTTPS
# (except for those URLs matching a regular expression listed in SECURE_REDIRECT_EXEMPT).
SECURE_SSL_REDIRECT = env('DD_SECURE_SSL_REDIRECT')

# If True, the SecurityMiddleware sets the X-XSS-Protection: 1;
# mode=block header on all responses that do not already have it.
SECURE_BROWSER_XSS_FILTER = env('DD_SECURE_BROWSER_XSS_FILTER')

# If True, the SecurityMiddleware sets the X-Content-Type-Options: nosniff;
SECURE_CONTENT_TYPE_NOSNIFF = env('DD_SECURE_CONTENT_TYPE_NOSNIFF')

# Whether to use HTTPOnly flag on the session cookie.
# If this is set to True, client-side JavaScript will not to be able to access the session cookie.
SESSION_COOKIE_HTTPONLY = env('DD_SESSION_COOKIE_HTTPONLY')

# Whether to use HttpOnly flag on the CSRF cookie. If this is set to True,
# client-side JavaScript will not to be able to access the CSRF cookie.
CSRF_COOKIE_HTTPONLY = env('DD_CSRF_COOKIE_HTTPONLY')

# Whether to use a secure cookie for the session cookie. If this is set to True,
# the cookie will be marked as secure, which means browsers may ensure that the
# cookie is only sent with an HTTPS connection.
SESSION_COOKIE_SECURE = env('DD_SESSION_COOKIE_SECURE')

# Whether to use a secure cookie for the CSRF cookie.
CSRF_COOKIE_SECURE = env('DD_CSRF_COOKIE_SECURE')

if env('DD_SECURE_PROXY_SSL_HEADER'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if env('DD_SECURE_HSTS_INCLUDE_SUBDOMAINS'):
    SECURE_HSTS_SECONDS = env('DD_SECURE_HSTS_SECONDS')
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env('DD_SECURE_HSTS_INCLUDE_SUBDOMAINS')

SESSION_EXPIRE_AT_BROWSER_CLOSE = env('DD_SESSION_EXPIRE_AT_BROWSER_CLOSE')
SESSION_COOKIE_AGE = env('DD_SESSION_COOKIE_AGE')

# ------------------------------------------------------------------------------
# DEFECTDOJO SPECIFIC
# ------------------------------------------------------------------------------

# Credential Key
CREDENTIAL_AES_256_KEY = env('DD_CREDENTIAL_AES_256_KEY')
DB_KEY = env('DD_CREDENTIAL_AES_256_KEY')

# Used in a few places to prefix page headings and in email salutations
TEAM_NAME = env('DD_TEAM_NAME')

# Used to configure a custom version in the footer of the base.html template.
FOOTER_VERSION = env('DD_FOOTER_VERSION')

# Django-tagging settings
FORCE_LOWERCASE_TAGS = env('DD_FORCE_LOWERCASE_TAGS')
MAX_TAG_LENGTH = env('DD_MAX_TAG_LENGTH')


# ------------------------------------------------------------------------------
# ADMIN
# ------------------------------------------------------------------------------
from email.utils import getaddresses
ADMINS = getaddresses([env('DD_ADMINS')])

# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# Django admin enabled
DJANGO_ADMIN_ENABLED = env('DD_DJANGO_ADMIN_ENABLED')

# ------------------------------------------------------------------------------
# API V2
# ------------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.DjangoModelPermissions',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 25
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'api_key': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization'
        }
    },
    'DOC_EXPANSION': "none",
    'JSON_EDITOR': True,
    'SHOW_REQUEST_HEADERS': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Defect Dojo API v2',
    'DESCRIPTION': 'Defect Dojo - Open Source vulnerability Management made easy. Prefetch related parameters/responses not yet in the schema.',
    'VERSION': __version__,
    # OTHER SETTINGS
    # the following set to False could help some client generators
    # 'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': False,
    'POSTPROCESSING_HOOKS': ['dojo.api_v2.prefetch.schema.prefetch_postprocessing_hook']
}

# ------------------------------------------------------------------------------
# TEMPLATES
# ------------------------------------------------------------------------------

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': env('DD_DEBUG'),
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                'dojo.context_processors.globalize_oauth_vars',
                'dojo.context_processors.bind_system_settings',
                'dojo.context_processors.bind_alert_count',
            ],
        },
    },
]

# ------------------------------------------------------------------------------
# APPS
# ------------------------------------------------------------------------------

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'polymorphic',  # provides admin templates
    'django.contrib.admin',
    'django.contrib.humanize',
    'gunicorn',
    'auditlog',
    'dojo',
    'watson',
    'tagging',  # not used, but still needed for migration 0065_django_tagulous.py (v1.10.0)
    'imagekit',
    'multiselectfield',
    'rest_framework',
    'rest_framework.authtoken',
    'dbbackup',
    'django_celery_results',
    'social_django',
    'drf_yasg',
    'drf_spectacular',
    'tagulous'
)

# ------------------------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------------------------
DJANGO_MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'dojo.middleware.DojoSytemSettingsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dojo.middleware.LoginRequiredMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'watson.middleware.SearchContextMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'crum.CurrentRequestUserMiddleware',
    'dojo.request_cache.middleware.RequestCacheMiddleware',
]

MIDDLEWARE = DJANGO_MIDDLEWARE_CLASSES

# WhiteNoise allows your web app to serve its own static files,
# making it a self-contained unit that can be deployed anywhere without relying on nginx
if env('DD_WHITENOISE'):
    WHITE_NOISE = [
        # Simplified static file serving.
        # https://warehouse.python.org/project/whitenoise/
        'whitenoise.middleware.WhiteNoiseMiddleware',
    ]
    MIDDLEWARE = MIDDLEWARE + WHITE_NOISE

EMAIL_CONFIG = env.email_url(
    'DD_EMAIL_URL', default='smtp://user@:password@localhost:25')

vars().update(EMAIL_CONFIG)

# ------------------------------------------------------------------------------
# SAML
# ------------------------------------------------------------------------------
# For more configuration and customization options, see djangosaml2 documentation
# https://djangosaml2.readthedocs.io/contents/setup.html#configuration
# To override not configurable settings, you can use local_settings.py
SAML2_ENABLED = env('DD_SAML2_ENABLED')
SAML2_LOGOUT_URL = env('DD_SAML2_LOGOUT_URL')
if SAML2_ENABLED:
    import saml2
    import saml2.saml
    from os import path
    # SSO_URL = env('DD_SSO_URL')
    SAML_METADATA = {}
    if len(env('DD_SAML2_METADATA_AUTO_CONF_URL')) > 0:
        SAML_METADATA['remote'] = [{"url": env('DD_SAML2_METADATA_AUTO_CONF_URL')}]
    if len(env('DD_SAML2_METADATA_LOCAL_FILE_PATH')) > 0:
        SAML_METADATA['local'] = [env('DD_SAML2_METADATA_LOCAL_FILE_PATH')]
    INSTALLED_APPS += ('djangosaml2',)
    MIDDLEWARE.append('djangosaml2.middleware.SamlSessionMiddleware')
    AUTHENTICATION_BACKENDS += ('djangosaml2.backends.Saml2Backend',)
    LOGIN_EXEMPT_URLS += (r'^%ssaml2/' % URL_PREFIX,)
    SAML_LOGOUT_REQUEST_PREFERRED_BINDING = saml2.BINDING_HTTP_POST
    SAML_IGNORE_LOGOUT_ERRORS = True
    SAML_DJANGO_USER_MAIN_ATTRIBUTE = 'username'
    # SAML_DJANGO_USER_MAIN_ATTRIBUTE_LOOKUP = '__iexact'
    SAML_USE_NAME_ID_AS_USERNAME = True
    SAML_CREATE_UNKNOWN_USER = env('DD_SAML2_CREATE_USER')
    SAML_ATTRIBUTE_MAPPING = env('DD_SAML2_ATTRIBUTES_MAP')
    BASEDIR = path.dirname(path.abspath(__file__))
    if len(env('DD_SAML2_ENTITY_ID')) == 0:
        SAML2_ENTITY_ID = '%s/saml2/metadata/' % SITE_URL
    else:
        SAML2_ENTITY_ID = env('DD_SAML2_ENTITY_ID')

    SAML_CONFIG = {
        # full path to the xmlsec1 binary programm
        'xmlsec_binary': '/usr/bin/xmlsec1',

        # your entity id, usually your subdomain plus the url to the metadata view
        'entityid': '%s' % SAML2_ENTITY_ID,

        # directory with attribute mapping
        'attribute_map_dir': path.join(BASEDIR, 'attribute-maps'),

        # this block states what services we provide
        'service': {
            # we are just a lonely SP
            'sp': {
                'name': 'Defect_Dojo',
                'name_id_format': saml2.saml.NAMEID_FORMAT_TRANSIENT,
                'want_response_signed': False,
                'want_assertions_signed': True,
                'force_authn': True,
                'allow_unsolicited': True,

                # For Okta add signed logout requets. Enable this:
                # "logout_requests_signed": True,

                'endpoints': {
                    # url and binding to the assetion consumer service view
                    # do not change the binding or service name
                    'assertion_consumer_service': [
                        ('%s/saml2/acs/' % SITE_URL,
                        saml2.BINDING_HTTP_POST),
                    ],
                    # url and binding to the single logout service view
                    # do not change the binding or service name
                    'single_logout_service': [
                        # Disable next two lines for HTTP_REDIRECT for IDP's that only support HTTP_POST. Ex. Okta:
                        ('%s/saml2/ls/' % SITE_URL,
                        saml2.BINDING_HTTP_REDIRECT),
                        ('%s/saml2/ls/post' % SITE_URL,
                        saml2.BINDING_HTTP_POST),
                    ],
                },

                # attributes that this project need to identify a user
                'required_attributes': ['Email', 'UserName'],

                # attributes that may be useful to have but not required
                'optional_attributes': ['Firstname', 'Lastname'],

                # in this section the list of IdPs we talk to are defined
                # This is not mandatory! All the IdP available in the metadata will be considered.
                # 'idp': {
                #     # we do not need a WAYF service since there is
                #     # only an IdP defined here. This IdP should be
                #     # present in our metadata

                #     # the keys of this dictionary are entity ids
                #     'https://localhost/simplesaml/saml2/idp/metadata.php': {
                #         'single_sign_on_service': {
                #             saml2.BINDING_HTTP_REDIRECT: 'https://localhost/simplesaml/saml2/idp/SSOService.php',
                #         },
                #         'single_logout_service': {
                #             saml2.BINDING_HTTP_REDIRECT: 'https://localhost/simplesaml/saml2/idp/SingleLogoutService.php',
                #         },
                #     },
                # },
            },
        },

        # where the remote metadata is stored, local, remote or mdq server.
        # One metadatastore or many ...
        'metadata': SAML_METADATA,

        # set to 1 to output debugging information
        'debug': 0,

        # Signing
        # 'key_file': path.join(BASEDIR, 'private.key'),  # private part
        # 'cert_file': path.join(BASEDIR, 'public.pem'),  # public part

        # Encryption
        # 'encryption_keypairs': [{
        #     'key_file': path.join(BASEDIR, 'private.key'),  # private part
        #     'cert_file': path.join(BASEDIR, 'public.pem'),  # public part
        # }],

        # own metadata settings
        'contact_person': [
            {'given_name': 'Lorenzo',
            'sur_name': 'Gil',
            'company': 'Yaco Sistemas',
            'email_address': 'lgs@yaco.es',
            'contact_type': 'technical'},
            {'given_name': 'Angel',
            'sur_name': 'Fernandez',
            'company': 'Yaco Sistemas',
            'email_address': 'angel@yaco.es',
            'contact_type': 'administrative'},
        ],
        # you can set multilanguage information here
        'organization': {
            'name': [('Yaco Sistemas', 'es'), ('Yaco Systems', 'en')],
            'display_name': [('Yaco', 'es'), ('Yaco', 'en')],
            'url': [('http://www.yaco.es', 'es'), ('http://www.yaco.com', 'en')],
        },
        'valid_for': 24,  # how long is our metadata valid
    }

# ------------------------------------------------------------------------------
# CELERY
# ------------------------------------------------------------------------------

# Celery settings
CELERY_BROKER_URL = env('DD_CELERY_BROKER_URL') \
    if len(env('DD_CELERY_BROKER_URL')) > 0 else generate_url(
    env('DD_CELERY_BROKER_SCHEME'),
    True,
    env('DD_CELERY_BROKER_USER'),
    env('DD_CELERY_BROKER_PASSWORD'),
    env('DD_CELERY_BROKER_HOST'),
    env('DD_CELERY_BROKER_PORT'),
    env('DD_CELERY_BROKER_PATH'),
    env('DD_CELERY_BROKER_PARAMS')
)
CELERY_TASK_IGNORE_RESULT = env('DD_CELERY_TASK_IGNORE_RESULT')
CELERY_RESULT_BACKEND = env('DD_CELERY_RESULT_BACKEND')
CELERY_TIMEZONE = TIME_ZONE
CELERY_RESULT_EXPIRES = env('DD_CELERY_RESULT_EXPIRES')
CELERY_BEAT_SCHEDULE_FILENAME = env('DD_CELERY_BEAT_SCHEDULE_FILENAME')
CELERY_ACCEPT_CONTENT = ['pickle', 'json', 'msgpack', 'yaml']
CELERY_TASK_SERIALIZER = env('DD_CELERY_TASK_SERIALIZER')
CELERY_PASS_MODEL_BY_ID = env('DD_CELERY_PASS_MODEL_BY_ID')

CELERY_IMPORTS = ('dojo.tools.tool_issue_updater', )

# Celery beat scheduled tasks
CELERY_BEAT_SCHEDULE = {
    'add-alerts': {
        'task': 'dojo.tasks.add_alerts',
        'schedule': timedelta(hours=1),
        'args': [timedelta(hours=1)]
    },
    'cleanup-alerts': {
        'task': 'dojo.tasks.cleanup_alerts',
        'schedule': timedelta(hours=8),
    },
    'dedupe-delete': {
        'task': 'dojo.tasks.async_dupe_delete',
        'schedule': timedelta(minutes=1),
        'args': [timedelta(minutes=1)]
    },
    'update-findings-from-source-issues': {
        'task': 'dojo.tools.tool_issue_updater.update_findings_from_source_issues',
        'schedule': timedelta(hours=3),
    },
    'compute-sla-age-and-notify': {
        'task': 'dojo.tasks.async_sla_compute_and_notify_task',
        'schedule': crontab(hour=7, minute=30),
    },
    'risk_acceptance_expiration_handler': {
        'task': 'dojo.risk_acceptance.helper.expiration_handler',
        'schedule': crontab(minute=0, hour='*/3'),  # every 3 hours
    },
    # 'jira_status_reconciliation': {
    #     'task': 'dojo.tasks.jira_status_reconciliation_task',
    #     'schedule': timedelta(hours=12),
    #     'kwargs': {'mode': 'reconcile', 'dryrun': True, 'daysback': 10, 'product': None, 'engagement': None}
    # },
    # 'fix_loop_duplicates': {
    #     'task': 'dojo.tasks.fix_loop_duplicates_task',
    #     'schedule': timedelta(hours=12)
    # },


}

# ------------------------------------
# Monitoring Metrics
# ------------------------------------
# address issue when running ./manage.py collectstatic
# reference: https://github.com/korfuri/django-prometheus/issues/34
PROMETHEUS_EXPORT_MIGRATIONS = False
# django metrics for monitoring
if env('DD_DJANGO_METRICS_ENABLED'):
    DJANGO_METRICS_ENABLED = env('DD_DJANGO_METRICS_ENABLED')
    INSTALLED_APPS = INSTALLED_APPS + ('django_prometheus',)
    MIDDLEWARE = ['django_prometheus.middleware.PrometheusBeforeMiddleware', ] + \
        MIDDLEWARE + \
        ['django_prometheus.middleware.PrometheusAfterMiddleware', ]
    database_engine = DATABASES.get('default').get('ENGINE')
    DATABASES['default']['ENGINE'] = database_engine.replace('django.', 'django_prometheus.', 1)
    # CELERY_RESULT_BACKEND.replace('django.core','django_prometheus.', 1)
    LOGIN_EXEMPT_URLS += (r'^%sdjango_metrics/' % URL_PREFIX,)


# ------------------------------------
# Hashcode configuration
# ------------------------------------
# List of fields used to compute the hash_code
# The fields must be one of HASHCODE_ALLOWED_FIELDS
# If not present, default is the legacy behavior: see models.py, compute_hash_code_legacy function
# legacy is:
#   static scanner:  ['title', 'cwe', 'line', 'file_path', 'description']
#   dynamic scanner: ['title', 'cwe', 'line', 'file_path', 'description']
HASHCODE_FIELDS_PER_SCANNER = {
    # In checkmarx, same CWE may appear with different severities: example "sql injection" (high) and "blind sql injection" (low).
    # Including the severity in the hash_code keeps those findings not duplicate
    'Anchore Engine Scan': ['title', 'severity', 'component_name', 'component_version', 'file_path'],
    'Anchore Grype': ['title', 'severity', 'component_name', 'component_version'],
    'Aqua Scan': ['severity', 'cve', 'component_name', 'component_version'],
    'CargoAudit Scan': ['cve', 'severity', 'component_name', 'component_version', 'vuln_id_from_tool'],
    'Checkmarx Scan': ['cwe', 'severity', 'file_path'],
    'Checkmarx OSA': ['cve', 'component_name'],
    'SonarQube Scan': ['cwe', 'severity', 'file_path'],
    'Dependency Check Scan': ['cve', 'cwe', 'file_path'],
    'Dependency Track Finding Packaging Format (FPF) Export': ['component_name', 'component_version', 'cwe', 'cve'],
    'Nessus Scan': ['title', 'severity', 'cve', 'cwe'],
    'Nexpose Scan': ['title', 'severity', 'cve', 'cwe'],
    # possible improvement: in the scanner put the library name into file_path, then dedup on cwe + file_path + severity
    'NPM Audit Scan': ['title', 'severity', 'file_path', 'cve', 'cwe'],
    # possible improvement: in the scanner put the library name into file_path, then dedup on cwe + file_path + severity
    'Yarn Audit Scan': ['title', 'severity', 'file_path', 'cve', 'cwe'],
    # possible improvement: in the scanner put the library name into file_path, then dedup on cve + file_path + severity
    'Whitesource Scan': ['title', 'severity', 'description'],
    'ZAP Scan': ['title', 'cwe', 'severity'],
    'Qualys Scan': ['title', 'severity'],
    # 'Qualys Webapp Scan': ['title', 'unique_id_from_tool'],
    'PHP Symfony Security Check': ['title', 'cve'],
    'Clair Scan': ['title', 'cve', 'description', 'severity'],
    'Clair Klar Scan': ['title', 'description', 'severity'],
    # for backwards compatibility because someone decided to rename this scanner:
    'Symfony Security Check': ['title', 'cve'],
    'DSOP Scan': ['cve'],
    'Acunetix Scan': ['title', 'description'],
    'Terrascan Scan': ['vuln_id_from_tool', 'title', 'severity', 'file_path', 'line', 'component_name'],
    'Trivy Scan': ['title', 'severity', 'cve', 'cwe'],
    'TFSec Scan': ['severity', 'vuln_id_from_tool', 'file_path', 'line'],
    'Snyk Scan': ['vuln_id_from_tool', 'file_path', 'component_name', 'component_version'],
    'GitLab Dependency Scanning Report': ['title', 'cve', 'file_path', 'component_name', 'component_version'],
    'SpotBugs Scan': ['cwe', 'severity', 'file_path', 'line'],
    'JFrog Xray Unified Scan': ['cve', 'file_path', 'component_name', 'component_version'],
    'Scout Suite Scan': ['title', 'severity', 'description'],
    'AWS Security Hub Scan': ['unique_id_from_tool'],
    'Meterian Scan': ['cwe', 'component_name', 'component_version', 'description', 'severity']
}

# This tells if we should accept cwe=0 when computing hash_code with a configurable list of fields from HASHCODE_FIELDS_PER_SCANNER (this setting doesn't apply to legacy algorithm)
# If False and cwe = 0, then the hash_code computation will fallback to legacy algorithm for the concerned finding
# Default is True (if scanner is not configured here but is configured in HASHCODE_FIELDS_PER_SCANNER, it allows null cwe)
HASHCODE_ALLOWS_NULL_CWE = {
    'Anchore Engine Scan': True,
    'Anchore Grype': True,
    'Checkmarx Scan': False,
    'Checkmarx OSA': True,
    'SonarQube Scan': False,
    'Dependency Check Scan': True,
    'Nessus Scan': True,
    'Nexpose Scan': True,
    'NPM Audit Scan': True,
    'Yarn Audit Scan': True,
    'Whitesource Scan': True,
    'ZAP Scan': False,
    'Qualys Scan': True,
    'DSOP Scan': True,
    'Acunetix Scan': True,
    'Trivy Scan': True,
    'SpotBugs Scan': False,
    'Scout Suite Scan': True,
    'AWS Security Hub Scan': True,
    'Meterian Scan': True
}

# List of fields that are known to be usable in hash_code computation)
# 'endpoints' is a pseudo field that uses the endpoints (for dynamic scanners)
# 'unique_id_from_tool' is often not needed here as it can be used directly in the dedupe algorithm, but it's also possible to use it for hashing
HASHCODE_ALLOWED_FIELDS = ['title', 'cwe', 'cve', 'line', 'file_path', 'component_name', 'component_version', 'description', 'endpoints', 'unique_id_from_tool', 'severity', 'vuln_id_from_tool']

# ------------------------------------
# Deduplication configuration
# ------------------------------------
# List of algorithms
# legacy one with multiple conditions (default mode)
DEDUPE_ALGO_LEGACY = 'legacy'
# based on dojo_finding.unique_id_from_tool only (for checkmarx detailed, or sonarQube detailed for example)
DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL = 'unique_id_from_tool'
# based on dojo_finding.hash_code only
DEDUPE_ALGO_HASH_CODE = 'hash_code'
# unique_id_from_tool or hash_code
# Makes it possible to deduplicate on a technical id (same parser) and also on some functional fields (cross-parsers deduplication)
DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE = 'unique_id_from_tool_or_hash_code'

# Choice of deduplication algorithm per parser
# Key = the scan_type from factory.py (= the test_type)
# Default is DEDUPE_ALGO_LEGACY
DEDUPLICATION_ALGORITHM_PER_PARSER = {
    'Anchore Engine Scan': DEDUPE_ALGO_HASH_CODE,
    'Anchore Grype': DEDUPE_ALGO_HASH_CODE,
    'Aqua Scan': DEDUPE_ALGO_HASH_CODE,
    'AuditJS Scan': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'Burp REST API': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'CargoAudit Scan': DEDUPE_ALGO_HASH_CODE,
    'Checkmarx Scan detailed': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'Checkmarx Scan': DEDUPE_ALGO_HASH_CODE,
    'Checkmarx OSA': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE,
    'Coverity API': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'Dependency Track Finding Packaging Format (FPF) Export': DEDUPE_ALGO_HASH_CODE,
    'SonarQube Scan detailed': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'SonarQube Scan': DEDUPE_ALGO_HASH_CODE,
    'Dependency Check Scan': DEDUPE_ALGO_HASH_CODE,
    'Nessus Scan': DEDUPE_ALGO_HASH_CODE,
    'Nexpose Scan': DEDUPE_ALGO_HASH_CODE,
    'NPM Audit Scan': DEDUPE_ALGO_HASH_CODE,
    'Yarn Audit Scan': DEDUPE_ALGO_HASH_CODE,
    'Whitesource Scan': DEDUPE_ALGO_HASH_CODE,
    'ZAP Scan': DEDUPE_ALGO_HASH_CODE,
    'Qualys Scan': DEDUPE_ALGO_HASH_CODE,
    'PHP Symfony Security Check': DEDUPE_ALGO_HASH_CODE,
    'Acunetix Scan': DEDUPE_ALGO_HASH_CODE,
    'Clair Scan': DEDUPE_ALGO_HASH_CODE,
    'Clair Klar Scan': DEDUPE_ALGO_HASH_CODE,
    # 'Qualys Webapp Scan': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,  # Must also uncomment qualys webapp line in hashcode fields per scanner
    'Veracode Scan': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE,
    # for backwards compatibility because someone decided to rename this scanner:
    'Symfony Security Check': DEDUPE_ALGO_HASH_CODE,
    'DSOP Scan': DEDUPE_ALGO_HASH_CODE,
    'Terrascan Scan': DEDUPE_ALGO_HASH_CODE,
    'Trivy Scan': DEDUPE_ALGO_HASH_CODE,
    'TFSec Scan': DEDUPE_ALGO_HASH_CODE,
    'HackerOne Cases': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE,
    'Snyk Scan': DEDUPE_ALGO_HASH_CODE,
    'GitLab Dependency Scanning Report': DEDUPE_ALGO_HASH_CODE,
    'Safety Scan': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'GitLab SAST Report': DEDUPE_ALGO_HASH_CODE,
    'Checkov Scan': DEDUPE_ALGO_HASH_CODE,
    'SpotBugs Scan': DEDUPE_ALGO_HASH_CODE,
    'JFrog Xray Unified Scan': DEDUPE_ALGO_HASH_CODE,
    'Scout Suite Scan': DEDUPE_ALGO_HASH_CODE,
    'AWS Security Hub Scan': DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL,
    'Meterian Scan': DEDUPE_ALGO_HASH_CODE
}

DUPE_DELETE_MAX_PER_RUN = env('DD_DUPE_DELETE_MAX_PER_RUN')

DISABLE_FINDING_MERGE = env('DD_DISABLE_FINDING_MERGE')

TRACK_IMPORT_HISTORY = env('DD_TRACK_IMPORT_HISTORY')

# ------------------------------------------------------------------------------
# JIRA
# ------------------------------------------------------------------------------
# The 'Bug' issue type is mandatory, as it is used as the default choice.
JIRA_ISSUE_TYPE_CHOICES_CONFIG = (
    ('Task', 'Task'),
    ('Story', 'Story'),
    ('Epic', 'Epic'),
    ('Spike', 'Spike'),
    ('Bug', 'Bug'),
    ('Security', 'Security')
)

JIRA_SSL_VERIFY = env('DD_JIRA_SSL_VERIFY')

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING_HANDLER = env('DD_LOGGING_HANDLER')

LOG_LEVEL = env('DD_LOG_LEVEL')
if not LOG_LEVEL:
    LOG_LEVEL = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            'datefmt': '%d/%b/%Y %H:%M:%S',
        },
        'simple': {
            'format': '%(levelname)s %(funcName)s %(lineno)d %(message)s'
        },
        'json': {
            '()': 'json_log_formatter.JSONFormatter',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue'
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'json_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins', 'console'],
            'level': 'WARN',
            'propagate': True,
        },
        'django.security': {
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': '%s' % LOG_LEVEL,
            'propagate': False,
        },
        'celery': {
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': '%s' % LOG_LEVEL,
            'propagate': False,
            # workaround some celery logging known issue
            'worker_hijack_root_logger': False,
        },
        'dojo': {
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': '%s' % LOG_LEVEL,
            'propagate': False,
        },
        'dojo.specific-loggers.deduplication': {
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': '%s' % LOG_LEVEL,
            'propagate': False,
        },
        'MARKDOWN': {
            # The markdown library is too verbose in it's logging, reducing the verbosity in our logs.
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': 'WARNING',
            'propagate': False,
        },
        'titlecase': {
            # The titlecase library is too verbose in it's logging, reducing the verbosity in our logs.
            'handlers': [r'%s' % LOGGING_HANDLER],
            'level': 'WARNING',
            'propagate': False,
        },
    }
}

# override filter to ensure sensitive variables are also hidden when DEBUG = True
DEFAULT_EXCEPTION_REPORTER_FILTER = 'dojo.settings.exception_filter.CustomExceptionReporterFilter'

# As we require `innodb_large_prefix = ON` for MySQL, we can silence the
# warning about large varchar with unique indices.
SILENCED_SYSTEM_CHECKS = ['mysql.E001']

# Issue on benchmark : "The number of GET/POST parameters exceeded settings.DATA_UPLOAD_MAX_NUMBER_FIELD S"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# Maximum size of a scan file in MB
SCAN_FILE_MAX_SIZE = 100

# Apply a severity level to "Security Weaknesses" in Qualys WAS
QUALYS_WAS_WEAKNESS_IS_VULN = env("DD_QUALYS_WAS_WEAKNESS_IS_VULN")

# Create a unique finding for all findings in qualys WAS parser
# If using this, lines for Qualys WAS deduplication functions must be un-commented
QUALYS_WAS_UNIQUE_ID = False

SERIALIZATION_MODULES = {
    'xml': 'tagulous.serializers.xml_serializer',
    'json': 'tagulous.serializers.json',
    'python': 'tagulous.serializers.python',
    'yaml': 'tagulous.serializers.pyyaml',
}

# There seems to be no way just use the default and just leave out jquery, so we have to copy...
# ... and keep it up-to-date.
TAGULOUS_AUTOCOMPLETE_JS = (
    # 'tagulous/lib/jquery.js',
    'tagulous/lib/select2-4/js/select2.full.min.js',
    'tagulous/tagulous.js',
    'tagulous/adaptor/select2-4.js',
)

# using 'element' for width should take width from css defined in template, but it doesn't. So set to 70% here.
TAGULOUS_AUTOCOMPLETE_SETTINGS = {'placeholder': "Enter some tags (comma separated, use enter to select / create a new tag)", 'width': '70%'}

# Feature toggle for new authorization, which is incomplete at the moment.
# Don't set it to True for productive environments!
FEATURE_AUTHORIZATION_V2 = env('DD_FEATURE_AUTHORIZATION_V2')
# When enabled, staff users have full access to all product types and products
AUTHORIZATION_STAFF_OVERRIDE = env('DD_AUTHORIZATION_STAFF_OVERRIDE')

EDITABLE_MITIGATED_DATA = env('DD_EDITABLE_MITIGATED_DATA')

USE_L10N = True

FEATURE_FINDING_GROUPS = env('DD_FEATURE_FINDING_GROUPS')
JIRA_TEMPLATE_ROOT = env('DD_JIRA_TEMPLATE_ROOT')
TEMPLATE_DIR_PREFIX = env('DD_TEMPLATE_DIR_PREFIX')

DUPLICATE_CLUSTER_CASCADE_DELETE = env('DD_DUPLICATE_CLUSTER_CASCADE_DELETE')
