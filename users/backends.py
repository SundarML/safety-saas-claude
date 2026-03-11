# users/backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmployeeIdPinBackend(BaseBackend):
    """
    Authenticate a worker-account using:
        organisation domain  +  employee_id  +  PIN
    Only works for accounts that have no email (worker accounts).
    """

    def authenticate(self, request, employee_id=None, pin=None, org_domain=None):
        if not employee_id or not pin or not org_domain:
            return None
        try:
            user = User.objects.select_related("organization").get(
                employee_id__iexact=employee_id.strip(),
                organization__domain__iexact=org_domain.strip(),
                is_active=True,
            )
        except User.DoesNotExist:
            # Run the hasher anyway to mitigate timing attacks
            User().check_pin("dummy")
            return None

        if user.check_pin(pin):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
