from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable

import requests

logger = logging.getLogger(__name__)

MAX_AI_CALLS_PER_RUN = 25
_ai_call_counter: int = 0


def _check_call_limit() -> None:
    global _ai_call_counter
    if _ai_call_counter >= MAX_AI_CALLS_PER_RUN:
        raise RuntimeError(
            f"AI call limit of {MAX_AI_CALLS_PER_RUN} reached per run"
        )
    _ai_call_counter += 1


def reset_call_counter() -> None:
    global _ai_call_counter
    _ai_call_counter = 0


@dataclass
class RetryConfig:
    max_attempts: int = 4
    base_delay: float = 2.0
    timeout: float = 30.0
    retryable_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )
    jitter: bool = True


def _should_retry_on_status(status: int, config: RetryConfig) -> bool:
    return status in config.retryable_statuses


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    if not config.jitter:
        return config.base_delay * (2 ** (attempt - 1))
    min_delay = config.base_delay * (2 ** (attempt - 1))
    max_delay = config.base_delay * (2 ** attempt)
    return random.uniform(min_delay, max_delay)


def retry_request(
    make_request: Callable[[], requests.Response],
    provider_name: str,
    config: RetryConfig | None = None,
) -> requests.Response:
    if config is None:
        config = RetryConfig()

    _check_call_limit()

    last_exc: Exception | None = None

    for attempt in range(1, config.max_attempts + 1):
        logger.info("%s request started (attempt %d/%d)", provider_name, attempt, config.max_attempts)

        try:
            resp = make_request()

        except requests.ConnectionError as exc:
            last_exc = exc
            if attempt < config.max_attempts:
                delay = _calculate_delay(attempt, config)
                logger.warning(
                    "%s connection error, retrying in %.1fs (attempt %d/%d)",
                    provider_name, delay, attempt + 1, config.max_attempts,
                )
                time.sleep(delay)
                continue
            logger.error("%s connection error, no more retries", provider_name)
            raise

        except requests.Timeout as exc:
            last_exc = exc
            if attempt < config.max_attempts:
                delay = _calculate_delay(attempt, config)
                logger.warning(
                    "%s timeout, retrying in %.1fs (attempt %d/%d)",
                    provider_name, delay, attempt + 1, config.max_attempts,
                )
                time.sleep(delay)
                continue
            logger.error("%s max retries exceeded after timeout", provider_name)
            raise

        except requests.RequestException as exc:
            last_exc = exc
            if attempt < config.max_attempts:
                delay = _calculate_delay(attempt, config)
                logger.warning(
                    "%s request error, retrying in %.1fs (attempt %d/%d): %s",
                    provider_name, delay, attempt + 1, config.max_attempts, exc,
                )
                time.sleep(delay)
                continue
            logger.error("%s max retries exceeded: %s", provider_name, exc)
            raise

        status = resp.status_code

        if 200 <= status < 300:
            logger.info("%s request succeeded", provider_name)
            return resp

        if _should_retry_on_status(status, config):
            if attempt < config.max_attempts:
                delay = float(resp.headers.get("Retry-After", str(_calculate_delay(attempt, config))))
                logger.warning(
                    "%s rate limited or server error (%d), retrying in %.1fs (attempt %d/%d)",
                    provider_name, status, delay, attempt + 1, config.max_attempts,
                )
                time.sleep(delay)
                continue
            logger.error("%s max retries exceeded (status %d)", provider_name, status)
            resp.raise_for_status()

        if status == 400:
            logger.error("%s bad request (400), no retry", provider_name)
        elif status == 401:
            logger.error("%s authentication failed (401), no retry", provider_name)
        elif status == 402:
            logger.error("%s quota exhausted (402), no retry", provider_name)
            raise ValueError(f"{provider_name} quota exhausted — skipping AI features")
        elif status == 403:
            logger.error("%s forbidden (403), no retry", provider_name)
        else:
            logger.error("%s client error (%d), no retry", provider_name, status)
        resp.raise_for_status()

    raise last_exc or RuntimeError(f"{provider_name} request failed after {config.max_attempts} attempts")
