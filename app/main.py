import ipaddress
from a2squery import AsyncA2SQuery
from a2squery.exceptions import InvalidResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore

def validate_host_address(host_address: str):
    try:
        ip = ipaddress.ip_address(host_address)
        if ip.is_private or ip.is_loopback:
            raise HTTPException(status_code=400, detail="Private or loopback IPs are not allowed")
    except ValueError:
        pass
    return host_address

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

@app.get("/info/{host_address}/")
@limiter.shared_limit("60/minute", "query")  # type: ignore
async def get_server_info(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(validate_host_address(host_address), port) as a2s:
        info = await a2s.info()
    return info

@app.get("/rules/{host_address}/")
@limiter.shared_limit("60/minute", "query")  # type: ignore
async def get_server_rules(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(validate_host_address(host_address), port) as a2s:
        rules = await a2s.rules()
    return rules

@app.get("/players/{host_address}/")
@limiter.shared_limit("60/minute", "query")  # type: ignore
async def get_server_players(request: Request, host_address: str, port: int = 27015):
    async with AsyncA2SQuery(validate_host_address(host_address), port) as a2s:
        players = await a2s.players()
    return players
