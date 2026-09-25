from .audit import log_action

# Ma'lumotni o'zgartiruvchi so'rovlar jurnalga avtomatik yoziladi.
# Batafsil (maydonlar kesimidagi) tarix alohida CaseEvent jadvalida saqlanadi.
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIP_PREFIXES = ("/tizim/kirish", "/tizim/chiqish", "/static/")


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method in WRITE_METHODS
            and getattr(request, "user", None) is not None
            and request.user.is_authenticated
            and not request.path.startswith(SKIP_PREFIXES)
            and not getattr(request, "_audit_logged", False)
        ):
            log_action(
                request,
                "so'rov",
                description=f"{request.method} {request.path} → {response.status_code}",
            )
        return response
