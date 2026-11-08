import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginIdentifierRateThrottle(SimpleRateThrottle):
    scope = "login_identifier"

    def get_cache_key(self, request, view):
        identifier = request.data.get("identifier", "")
        if not isinstance(identifier, str) or not identifier.strip():
            return None
        normalized = identifier.strip().lower()
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class LoginIPRateThrottle(SimpleRateThrottle):
    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
