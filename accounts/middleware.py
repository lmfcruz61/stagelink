import time

from django.conf import settings

from .models import ActivityLog


def _client_ip_address(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _trim(value, max_length):
    return (value or '')[:max_length]


class ActivityLogMiddleware:
    """
    Regista metadados de navegacao sem guardar corpos de pedidos.
    Isto evita capturar passwords, dados bancarios, chaves API ou mensagens privadas.
    """

    DEFAULT_EXCLUDED_PREFIXES = (
        '/static/',
        '/media/',
        '/favicon.ico',
        '/robots.txt',
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'ACTIVITY_LOG_ENABLED', True)
        self.excluded_prefixes = tuple(
            getattr(settings, 'ACTIVITY_LOG_EXCLUDED_PATH_PREFIXES', self.DEFAULT_EXCLUDED_PREFIXES)
        )

    def __call__(self, request):
        started_at = time.monotonic()
        response = None
        raised_exception = None

        try:
            response = self.get_response(request)
            return response
        except Exception as exc:
            raised_exception = exc
            raise
        finally:
            if self.enabled:
                self._write_log(request, response, raised_exception, started_at)

    def _write_log(self, request, response, raised_exception, started_at):
        path = request.path or ''
        if any(path.startswith(prefix) for prefix in self.excluded_prefixes):
            return

        status_code = getattr(response, 'status_code', None)
        if raised_exception is not None:
            status_code = 500

        user = getattr(request, 'user', None)
        if user is not None and not user.is_authenticated:
            user = None

        resolver_match = getattr(request, 'resolver_match', None)
        view_name = getattr(resolver_match, 'view_name', '') or ''

        try:
            ActivityLog.objects.create(
                user=user,
                username=(user.get_username() if user else ''),
                action=self._classify_action(request, status_code),
                method=_trim(request.method, 10),
                path=_trim(path, 500),
                query_string=_trim(request.META.get('QUERY_STRING', ''), 500),
                status_code=status_code,
                duration_ms=max(0, int((time.monotonic() - started_at) * 1000)),
                ip_address=_client_ip_address(request),
                user_agent=_trim(request.META.get('HTTP_USER_AGENT', ''), 255),
                referrer=_trim(request.META.get('HTTP_REFERER', ''), 500),
                view_name=_trim(view_name, 180),
            )
        except Exception:
            # O registo de auditoria nunca deve impedir o funcionamento do site.
            return

    def _classify_action(self, request, status_code):
        path = request.path.lower()
        method = request.method.upper()

        if status_code and status_code >= 400:
            return ActivityLog.ACTION_ERROR
        if path.startswith('/admin/'):
            return ActivityLog.ACTION_ADMIN
        if 'logout' in path:
            return ActivityLog.ACTION_LOGOUT
        if 'login' in path and method == 'POST':
            return ActivityLog.ACTION_LOGIN
        if path.startswith('/pagamentos/') or 'stripe' in path:
            return ActivityLog.ACTION_PAYMENT
        if method == 'POST' and ('upload' in path or 'galeria' in path or 'evento' in path):
            return ActivityLog.ACTION_UPLOAD
        return ActivityLog.ACTION_REQUEST
