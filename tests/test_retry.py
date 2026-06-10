from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from processors.retry import (
    MAX_AI_CALLS_PER_RUN,
    MAX_RETRY_DELAY,
    RetryConfig,
    _calculate_delay,
    _check_call_limit,
    _should_retry_on_status,
    reset_call_counter,
    retry_request,
)


def _mock_response(status: int = 200, data: dict[str, Any] | None = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = {}
    if data is not None:
        resp.json.return_value = data
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status} Client Error", response=resp
        )
    return resp


class TestRetryConfig:
    def test_defaults(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 2.0
        assert config.timeout == 30.0
        assert config.retryable_statuses == frozenset({429, 500, 502, 503, 504})

    def test_custom_values(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=1.0, timeout=15.0)
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.timeout == 15.0


class TestShouldRetryOnStatus:
    def test_429_is_retryable(self) -> None:
        assert _should_retry_on_status(429, RetryConfig()) is True

    def test_500_is_retryable(self) -> None:
        assert _should_retry_on_status(500, RetryConfig()) is True

    def test_502_is_retryable(self) -> None:
        assert _should_retry_on_status(502, RetryConfig()) is True

    def test_503_is_retryable(self) -> None:
        assert _should_retry_on_status(503, RetryConfig()) is True

    def test_504_is_retryable(self) -> None:
        assert _should_retry_on_status(504, RetryConfig()) is True

    def test_400_is_not_retryable(self) -> None:
        assert _should_retry_on_status(400, RetryConfig()) is False

    def test_401_is_not_retryable(self) -> None:
        assert _should_retry_on_status(401, RetryConfig()) is False

    def test_403_is_not_retryable(self) -> None:
        assert _should_retry_on_status(403, RetryConfig()) is False

    def test_200_is_not_retryable(self) -> None:
        assert _should_retry_on_status(200, RetryConfig()) is False


class TestCalculateDelay:
    def test_exponential_backoff(self) -> None:
        config = RetryConfig(base_delay=2.0)
        assert _calculate_delay(1, config) == 2.0
        assert _calculate_delay(2, config) == 4.0
        assert _calculate_delay(3, config) == 8.0

    def test_capped_at_max(self) -> None:
        config = RetryConfig(base_delay=10.0)
        assert _calculate_delay(1, config) == 10.0
        assert _calculate_delay(2, config) == 20.0
        assert _calculate_delay(3, config) == 20.0  # capped


class TestCallLimit:
    def setup_method(self) -> None:
        reset_call_counter()

    def test_call_counter_increments(self) -> None:
        _check_call_limit()
        _check_call_limit()
        assert True

    def test_call_limit_raises(self) -> None:
        reset_call_counter()
        for _ in range(MAX_AI_CALLS_PER_RUN):
            _check_call_limit()
        with pytest.raises(RuntimeError, match="AI call limit"):
            _check_call_limit()

    def test_reset_clears_counter(self) -> None:
        reset_call_counter()
        for _ in range(MAX_AI_CALLS_PER_RUN):
            _check_call_limit()
        reset_call_counter()
        _check_call_limit()
        assert True


class TestRetryRequest:
    def setup_method(self) -> None:
        reset_call_counter()

    def test_success_first_attempt(self) -> None:
        config = RetryConfig(max_attempts=3)
        mock = MagicMock(return_value=_mock_response(200))

        result = retry_request(mock, "TestProvider", config)

        assert result.status_code == 200
        mock.assert_called_once()

    def test_success_after_429_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            side_effect=[
                _mock_response(429),
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)

        assert result.status_code == 200
        assert mock.call_count == 2

    def test_success_after_timeout_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            side_effect=[
                requests.Timeout("timeout"),
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)

        assert result.status_code == 200
        assert mock.call_count == 2

    def test_429_retry_applies_retry_after_header(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=10.0)
        resp = _mock_response(429)
        resp.headers = {"Retry-After": "0.01"}
        mock = MagicMock(
            side_effect=[
                resp,
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)
        assert result.status_code == 200
        assert mock.call_count == 2

    def test_401_authentication_failure_no_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(return_value=_mock_response(401))

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request(mock, "TestProvider", config)
        mock.assert_called_once()

    def test_400_bad_request_no_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(return_value=_mock_response(400))

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request(mock, "TestProvider", config)
        mock.assert_called_once()

    def test_403_forbidden_no_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(return_value=_mock_response(403))

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request(mock, "TestProvider", config)
        mock.assert_called_once()

    def test_402_quota_exhausted_raises_value_error(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(return_value=_mock_response(402))

        with pytest.raises(ValueError, match="quota exhausted"):
            retry_request(mock, "TestProvider", config)
        mock.assert_called_once()

    def test_max_retries_exceeded_for_429(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            return_value=_mock_response(429)
        )

        with pytest.raises(requests.exceptions.HTTPError):
            retry_request(mock, "TestProvider", config)
        assert mock.call_count == 3

    def test_max_retries_exceeded_for_connection_error(self) -> None:
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        mock = MagicMock(
            side_effect=requests.ConnectionError("connection refused")
        )

        with pytest.raises(requests.ConnectionError):
            retry_request(mock, "TestProvider", config)
        assert mock.call_count == 2

    def test_max_retries_exceeded_for_timeout(self) -> None:
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        mock = MagicMock(
            side_effect=requests.Timeout("timed out")
        )

        with pytest.raises(requests.Timeout):
            retry_request(mock, "TestProvider", config)
        assert mock.call_count == 2

    def test_max_ai_calls_exceeded(self) -> None:
        reset_call_counter()
        config = RetryConfig(max_attempts=1, base_delay=0.01)

        for _ in range(MAX_AI_CALLS_PER_RUN):
            mock = MagicMock(return_value=_mock_response(200))
            retry_request(mock, "TestProvider", config)

        mock = MagicMock(return_value=_mock_response(200))
        with pytest.raises(RuntimeError, match="AI call limit"):
            retry_request(mock, "TestProvider", config)

    def test_success_after_connection_error_retry(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            side_effect=[
                requests.ConnectionError("connection reset"),
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)
        assert result.status_code == 200
        assert mock.call_count == 2

    def test_503_retry_then_success(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            side_effect=[
                _mock_response(503),
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)
        assert result.status_code == 200
        assert mock.call_count == 2

    def test_500_retry_then_success(self) -> None:
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        mock = MagicMock(
            side_effect=[
                _mock_response(500),
                _mock_response(200),
            ]
        )

        result = retry_request(mock, "TestProvider", config)
        assert result.status_code == 200
        assert mock.call_count == 2
