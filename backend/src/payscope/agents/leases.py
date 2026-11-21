import asyncio
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

LEASE_MS = 30_000
LEASE_COMMAND_SECONDS = 5

RESERVE = """
local time = redis.call('TIME')
local now = tonumber(time[1])*1000 + math.floor(tonumber(time[2])/1000)
local ttl = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
if redis.call('EXISTS', KEYS[3]) == 1 then return 1 end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[4]) then return 2 end
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[5]) then return 3 end
redis.call('SET', KEYS[3], ARGV[2], 'PX', ttl)
redis.call('ZADD', KEYS[1], now + ttl, ARGV[1])
redis.call('ZADD', KEYS[2], now + ttl, ARGV[1])
redis.call('PEXPIRE', KEYS[1], 2*ttl)
redis.call('PEXPIRE', KEYS[2], 2*ttl)
return 0
"""

RENEW = """
if redis.call('GET', KEYS[3]) ~= ARGV[2] then return 0 end
local time = redis.call('TIME')
local now = tonumber(time[1])*1000 + math.floor(tonumber(time[2])/1000)
local ttl = tonumber(ARGV[3])
redis.call('PEXPIRE', KEYS[3], ttl)
redis.call('ZADD', KEYS[1], now + ttl, ARGV[1])
redis.call('ZADD', KEYS[2], now + ttl, ARGV[1])
redis.call('PEXPIRE', KEYS[1], 2*ttl)
redis.call('PEXPIRE', KEYS[2], 2*ttl)
return 1
"""

RELEASE = """
if redis.call('GET', KEYS[3]) ~= ARGV[2] then return 0 end
redis.call('DEL', KEYS[3])
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""


class AdmissionUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Lease:
    user_id: UUID
    request_key: UUID
    owner: UUID

    @property
    def member(self) -> str:
        return f"{self.user_id}:{self.request_key}"


@dataclass(frozen=True)
class LeaseStore:
    redis: Redis
    namespace: str
    global_quota: int
    user_quota: int

    async def command(self, script: str, lease: Lease, *args: int) -> int:
        prefix = f"{{{self.namespace}:agents}}"
        keys = (
            f"{prefix}:pool",
            f"{prefix}:user:{lease.user_id}",
            f"{prefix}:owner:{lease.member}",
        )
        try:
            async with asyncio.timeout(LEASE_COMMAND_SECONDS):
                return await self.redis.eval(
                    script,
                    len(keys),
                    *keys,
                    lease.member,
                    str(lease.owner),
                    *args,
                )
        except RedisError, TimeoutError:
            raise AdmissionUnavailable from None

    async def reserve(self, lease: Lease) -> str | None:
        result = await self.command(
            RESERVE, lease, LEASE_MS, self.user_quota, self.global_quota
        )
        return (None, "ADMISSION_PENDING", "USER_CONCURRENCY_LIMIT", "AGENT_POOL_BUSY")[
            result
        ]

    async def renew(self, lease: Lease) -> bool:
        return bool(await self.command(RENEW, lease, LEASE_MS))

    async def release(self, lease: Lease) -> bool:
        return bool(await self.command(RELEASE, lease))
