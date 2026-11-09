from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.contrib.auth.models import User
from django.db import connection, connections
from django.utils import timezone

from common.exceptions import BusinessError
from content.models import Content, ContentAction, ContentRevision
from content.services import change_publication


pytestmark = pytest.mark.django_db(transaction=True)


def test_concurrent_publish_has_one_version_transition():
    if connection.vendor != "mysql":
        pytest.skip("requires MariaDB")
    actor = User.objects.create_user("cms_race")
    content = Content.objects.create(kind="banner", slug="race-banner")
    revision = ContentRevision.objects.create(
        content=content,
        revision_no=1,
        title="并发发布",
        blocks=[{"type": "text", "text": "正文"}],
        platforms=["web"],
        start_at=timezone.now() - timedelta(seconds=1),
        editor=actor,
    )
    gate = Barrier(2)

    def publish():
        try:
            gate.wait(timeout=30)
            return change_publication(
                actor,
                content.pk,
                {
                    "revision": revision.revision_no,
                    "expected_version": 1,
                    "reason": "竞争",
                },
                uuid4(),
                True,
            )
        except BusinessError as exc:
            return exc.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish(), range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count(10008) == 1
    content.refresh_from_db()
    assert content.version == 2 and content.published_revision_id == revision.pk
    assert (
        ContentAction.objects.filter(content=content, operation="publish").count() == 1
    )
