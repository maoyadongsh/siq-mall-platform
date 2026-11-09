from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_moderation(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.using(using).get_or_create(name="review_moderator")
    group.permissions.add(
        Permission.objects.using(using).get(
            content_type__app_label="reviews", codename="moderate"
        )
    )


class ReviewsConfig(AppConfig):
    name = "reviews"

    def ready(self):
        post_migrate.connect(
            grant_moderation, sender=self, dispatch_uid="reviews.grant_moderation"
        )
