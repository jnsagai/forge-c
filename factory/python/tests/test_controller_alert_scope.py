"""Additive exact-id local alert delivery; default path has inherited regressions."""

import pytest
from forge_factory.afo import alerts


@pytest.mark.parametrize("ids,limit", [((), 1), (("foreign",), 1), (("afo-ntf-" + "a" * 20,), 0), (("afo-ntf-" + "a" * 20,), 2)])
def test_invalid_scoped_delivery_never_opens_store(ids, limit):
    class Never:
        def tx(self):
            pytest.fail("invalid delivery scope touched Store")

    with pytest.raises(ValueError):
        alerts.deliver(Never(), adapters={}, notification_ids=ids, limit=limit)
