import pytest
from src.parser import parse_s2d


def test_parse_s2d_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        parse_s2d("nonexistent.xlsx")
