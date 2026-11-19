import asyncio
import json
from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

from payscope.analytics.schemas import ReportFilters, SalaryReport
from payscope.config import Settings

REPORT_CACHE_TTL = 60
MAX_REPORT_BYTES = 16 * 1024
CACHE_TIMEOUT_SECONDS = 1.5
SOCKET_TIMEOUT_SECONDS = 0.5


@dataclass(slots=True)
class ReportCache:
    redis: Redis
    prefix: str

    def key(self, filters: ReportFilters, revision: int) -> str:
        return (
            f"{self.prefix}:{revision}:{filters.country_code or '-'}:"
            f"{filters.department_id or '-'}:{filters.job_title_id or '-'}:{filters.group_by or '-'}"
        )

    async def get(self, filters: ReportFilters, revision: int) -> SalaryReport | None:
        async with asyncio.timeout(CACHE_TIMEOUT_SECONDS):
            data = await self.redis.get(self.key(filters, revision))
        if not data or len(data) > MAX_REPORT_BYTES:
            return None
        try:
            report = SalaryReport.model_validate_json(data)
        except ValidationError:
            return None
        return (
            report if report.revision == revision and report.group_by == filters.group_by else None
        )

    async def put(self, filters: ReportFilters, report: SalaryReport) -> None:
        if not report.rows:
            return
        data = json.dumps(report.model_dump(), default=str, separators=(",", ":")).encode()
        if len(data) <= MAX_REPORT_BYTES:
            async with asyncio.timeout(CACHE_TIMEOUT_SECONDS):
                await self.redis.set(self.key(filters, report.revision), data, ex=REPORT_CACHE_TTL)


def create_report_cache(settings: Settings) -> ReportCache | None:
    if settings.redis_url is None:
        return None
    database = settings.sqlalchemy_url
    namespace = sha256(
        repr((database.host, database.port, database.database, database.username)).encode()
    ).hexdigest()[:16]
    client = Redis.from_url(
        settings.redis_url.get_secret_value(),
        max_connections=10,
        socket_timeout=SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=CACHE_TIMEOUT_SECONDS,
        retry=Retry(NoBackoff(), 0),
        protocol=2,
        driver_info=None,
    )
    return ReportCache(client, f"payscope:reports:v1:{namespace}")
