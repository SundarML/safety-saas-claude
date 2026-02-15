# core/mixins.py
# Kept for backwards compatibility — new code uses OrgQuerySetMixin in observations/views.py
from django.core.exceptions import PermissionDenied
from observations.models import Observation


class OrganizationQuerySetMixin:
    """
    Scopes CBV querysets to the current organization.
    """
    def get_queryset(self):
        if not self.request.organization:
            raise PermissionDenied("You are not associated with any organization.")
        return Observation.objects.filter(organization=self.request.organization)
