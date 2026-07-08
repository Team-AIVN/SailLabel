"""Login signal handlers.

`core.middleware.InactivitySessionTimeoutMiddleWare` treats a missing
`session['last_login']` as "epoch 0" and force-logs-out the user when
`current_time - 0 > MAX_SESSION_AGE`. The project's local login wrapper
(`users.functions.common.login`) sets `last_login` explicitly, but any code path
that calls `django.contrib.auth.login` directly skips that wrapper.

Attaching a `user_logged_in` receiver guarantees `last_login` is populated for
every authentication path.
"""

from time import time

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def stamp_last_login_on_session(sender, request, user, **kwargs):
    if request is not None and hasattr(request, 'session'):
        request.session['last_login'] = time()
