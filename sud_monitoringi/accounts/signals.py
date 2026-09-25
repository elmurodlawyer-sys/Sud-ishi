from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import log_action


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_action(request, "kirish", user=user, description="Tizimga kirdi")


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_action(request, "chiqish", user=user, description="Tizimdan chiqdi")


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    log_action(
        request,
        "kirish_xato",
        username=(credentials or {}).get("username", "")[:150],
        description="Muvaffaqiyatsiz kirish urinishi",
    )
