import pytest
@pytest.mark.parametrize("v", ["x"*70], ids=["y"*90])
def test_very_long_parameter_id_for_width_check(v): assert False, "boom"
