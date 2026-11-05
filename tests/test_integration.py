import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from rankforge.core import FEATURES, Engine
from rankforge.api import create_app


@pytest.mark.integration
def test_real_embedding_ranker_and_api():
    path = os.getenv("TEST_BUNDLE")
    if not path:
        pytest.skip("Set TEST_BUNDLE to a real trained bundle")

    engine = Engine(path)
    assert engine.manifest["encoder"] == "sentence-transformers"
    assert engine.ranker is not None

    rankings, ids, x = engine.prepare("How do interest rates affect bond prices?")
    assert len(ids) > 0
    assert x.shape[1] == len(FEATURES)
    # The learned mode reorders hybrid's candidates; it never changes the set.
    assert {i for i, _ in rankings["hybrid"]} == {i for i, _ in rankings["ltr"]}

    reloaded = Engine(path, encoder=engine.encoder)
    np.testing.assert_allclose(engine.ranker.predict(x), reloaded.ranker.predict(x))

    with TestClient(create_app(engine=engine)) as c:
        assert c.get("/health/ready").status_code == 200
        assert c.get("/api/status").json()["ready"] is True
        for mode in engine.modes:
            response = c.get("/api/search", params={"q": "interest rates", "mode": mode})
            assert response.status_code == 200
            assert response.json()["results"]
