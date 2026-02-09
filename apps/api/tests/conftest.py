import sys
sys.path.insert(0, "/Users/claudevcheval/Hanalei/talent-promo/apps/api")

import pytest
from middleware import rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limit state and set high limits to prevent cross-test pollution.

    Tests that specifically test rate limiting should set their own limits.
    """
    rate_limit._rate_limits.clear()
    rate_limit._global_requests.clear()
    # Set high limits so non-rate-limit tests aren't affected
    original_per_ip = rate_limit.RATE_LIMIT_REQUESTS
    original_global = rate_limit.GLOBAL_DAILY_LIMIT
    rate_limit.RATE_LIMIT_REQUESTS = 9999
    rate_limit.GLOBAL_DAILY_LIMIT = 9999
    yield
    rate_limit._rate_limits.clear()
    rate_limit._global_requests.clear()
    rate_limit.RATE_LIMIT_REQUESTS = original_per_ip
    rate_limit.GLOBAL_DAILY_LIMIT = original_global
