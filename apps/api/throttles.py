from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class TokenRefreshRateThrottle(AnonRateThrottle):
    scope = "token_refresh"


class ActivityUploadRateThrottle(UserRateThrottle):
    scope = "activity_upload"


class WebhookRateThrottle(AnonRateThrottle):
    scope = "webhook"
