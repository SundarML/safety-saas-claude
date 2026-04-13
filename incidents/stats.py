# incidents/stats.py
from django.db.models import Sum, Count, Q
from .models import Incident, HoursWorked


def _total_hours(org, year):
    result = HoursWorked.objects.filter(
        organization=org, year=year
    ).aggregate(total=Sum("hours"))["total"]
    return float(result or 0)


def _rate(count, hours, multiplier=1_000_000):
    if not hours:
        return None
    return round(count * multiplier / hours, 2)


def calculate_stats(org, year):
    qs = Incident.objects.filter(organization=org, date_occurred__year=year)

    total_hours = _total_hours(org, year)

    lti_count  = qs.filter(severity=Incident.SEV_LTI).count()
    mtc_count  = qs.filter(severity=Incident.SEV_MTC).count()
    fac_count  = qs.filter(severity=Incident.SEV_FAC).count()
    fatal_count= qs.filter(severity=Incident.SEV_FATALITY).count()
    nm_count   = qs.filter(severity=Incident.SEV_NEAR_MISS).count()
    recordable = lti_count + mtc_count + fac_count + fatal_count

    days_lost  = qs.aggregate(total=Sum("days_lost"))["total"] or 0

    return {
        "total":        qs.count(),
        "fatalities":   fatal_count,
        "lti":          lti_count,
        "mtc":          mtc_count,
        "fac":          fac_count,
        "near_miss":    nm_count,
        "recordable":   recordable,
        "days_lost":    days_lost,
        "total_hours":  total_hours,
        # Rates (None if no hours entered)
        "ltifr":  _rate(lti_count,  total_hours),
        "trifr":  _rate(recordable, total_hours),
        "severity_rate": _rate(days_lost, total_hours),
    }


def get_monthly_trend(org, year):
    """Returns list of 12 dicts with month label + counts by severity group."""
    MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec"]
    results = []
    for m in range(1, 13):
        qs = Incident.objects.filter(
            organization=org, date_occurred__year=year, date_occurred__month=m
        )
        results.append({
            "month":     MONTH_LABELS[m - 1],
            "total":     qs.count(),
            "lti":       qs.filter(severity__in=[Incident.SEV_LTI, Incident.SEV_FATALITY]).count(),
            "mtc_fac":   qs.filter(severity__in=[Incident.SEV_MTC, Incident.SEV_FAC]).count(),
            "near_miss": qs.filter(severity=Incident.SEV_NEAR_MISS).count(),
            "property":  qs.filter(severity=Incident.SEV_PROPERTY).count(),
        })
    return results


def get_type_breakdown(org, year):
    qs = Incident.objects.filter(organization=org, date_occurred__year=year)
    rows = qs.values("incident_type").annotate(count=Count("id")).order_by("-count")
    label_map = dict(Incident.TYPE_CHOICES)
    return [{"label": label_map.get(r["incident_type"], r["incident_type"]),
             "count": r["count"]} for r in rows]


def get_location_breakdown(org, year):
    qs = Incident.objects.filter(organization=org, date_occurred__year=year)
    rows = (
        qs.values("location_text")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    return [{"label": r["location_text"] or "Unknown", "count": r["count"]} for r in rows]
