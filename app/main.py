import os
import asyncio
import socket
import ipaddress
from a2squery import AsyncA2SQuery
from a2squery.exceptions import InvalidResponse
from cashews import cache
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore

if os.getenv("REDIS_HOST"):
    cache_url = f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT', 6379)}"
else:
    cache_url = "mem://"

cache.setup(cache_url)

async def validate_host_address(host_address: str) -> str:
    try:
        loop = asyncio.get_running_loop()

        addr_info = await loop.getaddrinfo(
            host_address,
            None,
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM
        )

        resolved_ip = addr_info[0][4][0]

        ip = ipaddress.ip_address(resolved_ip)
        if ip.is_private or ip.is_loopback:
            raise HTTPException(status_code=400, detail="Private or loopback IPs are not allowed")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host address.")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Unable to resolve hostname.")
    
    return str(resolved_ip)

@app.exception_handler(TimeoutError)
async def timeout_handler(request: Request, exc: TimeoutError):
    return JSONResponse(
        status_code=504,
        content={"message": "Connection to gameserver timed out"},
    )

@app.exception_handler(InvalidResponse)
async def invalid_response_handler(request: Request, exc: TimeoutError):
    return JSONResponse(
        status_code=502,
        content={"message": "Unable to parse data from gameserver"},
    )

@app.get("/server/{host_address}/")
@limiter.limit("60/minute")  # type: ignore
@cache(ttl="15s", key="server:{host_address}:{port}")
async def get_all_server_info(request: Request, host_address: str, port: int = 27015) -> Dict[str, Any]:
    async with AsyncA2SQuery(await validate_host_address(host_address), port) as a2s:
        info, players, rules = await asyncio.gather(
            a2s.info(),
            a2s.players(),
            a2s.rules(),
            return_exceptions=True
        )

    if isinstance(info, Exception): raise info
    if isinstance(players, Exception): raise players
    if isinstance(rules, Exception): raise rules
    return {
        "info": info if not isinstance(info, Exception) else None,
        "players": players if not isinstance(players, Exception) else None,
        "rules": rules if not isinstance(rules, Exception) else None
    }

@app.get("/info/{host_address}/")
@limiter.shared_limit("180/minute", "query")  # type: ignore
@cache(ttl="15s", key="info:{host_address}:{port}")
async def get_server_info(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(await validate_host_address(host_address), port) as a2s:
        info = await a2s.info()
    return info

@app.get("/rules/{host_address}/")
@limiter.shared_limit("180/minute", "query")  # type: ignore
@cache(ttl="15s", key="rules:{host_address}:{port}")
async def get_server_rules(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(await validate_host_address(host_address), port) as a2s:
        rules = await a2s.rules()
    return rules

@app.get("/players/{host_address}/")
@limiter.shared_limit("180/minute", "query")  # type: ignore
@cache(ttl="15s", key="players:{host_address}:{port}")
async def get_server_players(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(await validate_host_address(host_address), port) as a2s:
        players = await a2s.players()
    return players
