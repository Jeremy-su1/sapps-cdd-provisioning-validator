"""Tests for src/collector/nsxt_dfw_collector.py — actual state collection interface."""
import pytest
from src.collector.nsxt_dfw_collector import NsxtDfwCollector, CollectorError


class TestCollectorInterface:
    def test_instantiates_without_error(self):
        collector = NsxtDfwCollector(host="nsxt.example.com", token="test-token")
        assert collector is not None

    def test_has_collect_method(self):
        collector = NsxtDfwCollector(host="nsxt.example.com", token="test-token")
        assert callable(collector.collect)

    def test_collect_raises_not_implemented_without_credentials(self):
        collector = NsxtDfwCollector(host=None, token=None)
        with pytest.raises(CollectorError):
            collector.collect()

    def test_collector_error_is_exception(self):
        assert issubclass(CollectorError, Exception)

    def test_dry_run_collect_returns_empty_list(self):
        collector = NsxtDfwCollector(host="nsxt.example.com", token="test-token", dry_run=True)
        result = collector.collect()
        assert result == []

    def test_dry_run_collect_returns_list_type(self):
        collector = NsxtDfwCollector(host="nsxt.example.com", token="test-token", dry_run=True)
        result = collector.collect()
        assert isinstance(result, list)

    def test_host_stored(self):
        collector = NsxtDfwCollector(host="nsxt.example.com", token="tok")
        assert collector.host == "nsxt.example.com"

    def test_dry_run_flag_stored(self):
        collector = NsxtDfwCollector(host="h", token="t", dry_run=True)
        assert collector.dry_run is True

    def test_dry_run_defaults_to_false(self):
        collector = NsxtDfwCollector(host="h", token="t")
        assert collector.dry_run is False
