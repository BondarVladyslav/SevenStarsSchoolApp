from decouple import config

R2_ENDPOINT_URL = config('R2_ENDPOINT_URL', default='')


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        connect_src = "connect-src 'self' ws: wss:"
        if R2_ENDPOINT_URL:
            connect_src += f" {R2_ENDPOINT_URL}"

        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('Referrer-Policy', 'same-origin')
        response.setdefault('Content-Security-Policy', (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com; "
            "img-src 'self' data:; "
            f"{connect_src};"
        ))

        return response