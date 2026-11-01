import pytest
@pytest.mark.parametrize("v", ["a - b","a - c","plain"], ids=["a - b","a - c","plain"])
def test_p(v): assert v == "plain"
def test_env(): raise AssertionError("expected 3 got 4")
def test_ok(): pass
