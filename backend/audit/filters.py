from django_filters import CharFilter, FilterSet, IsoDateTimeFilter


class AuditFilter(FilterSet):
    object_type = CharFilter()
    object_id = CharFilter()
    action = CharFilter()
    created_after = IsoDateTimeFilter()
    created_before = IsoDateTimeFilter()

    class Meta:
        fields: list[str] = []
