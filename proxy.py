
import asyncio
from aiohttp import web, ClientSession, WSMsgType
from multidict import CIMultiDict

FRONTEND = "http://127.0.0.1:5500"
BACKEND = "http://127.0.0.1:8000"

HOP_HEADERS = {
    "host", "connection", "keep-alive",
    "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade"
}


def clean_headers(headers):
    return {
        k: v for k, v in headers.items()
        if k.lower() not in HOP_HEADERS
    }


async def proxy_websocket(request, target):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_HEADERS
        and not k.lower().startswith("sec-websocket-")
    }

    ws_target = target.replace("http://", "ws://", 1)

    try:
        async with ClientSession() as session:
            async with session.ws_connect(
                ws_target, headers=headers
            ) as upstream:

                async def client_to_server():
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            await upstream.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await upstream.send_bytes(msg.data)
                        elif msg.type in (
                            WSMsgType.CLOSE,
                            WSMsgType.CLOSED,
                            WSMsgType.ERROR
                        ):
                            break

                async def server_to_client():
                    async for msg in upstream:
                        if msg.type == WSMsgType.TEXT:
                            await ws.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws.send_bytes(msg.data)
                        elif msg.type in (
                            WSMsgType.CLOSE,
                            WSMsgType.CLOSED,
                            WSMsgType.ERROR
                        ):
                            break

                tasks = [
                    asyncio.create_task(client_to_server()),
                    asyncio.create_task(server_to_client())
                ]

                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

    except Exception as error:
        print("WebSocket proxy error:", error)

    finally:
        await ws.close()

    return ws


async def handler(request):
    path = request.path

    if path == "/openapi.json":
        base = BACKEND
        backend_path = "/openapi.json"

    elif path == "/api/docs":
        base = BACKEND
        backend_path = "/docs"

    elif path.startswith("/api/docs/"):
        base = BACKEND
        backend_path = path[4:]

    elif path == "/api/redoc":
        base = BACKEND
        backend_path = "/redoc"

    elif path == "/api" or path.startswith("/api/"):
        base = BACKEND
        backend_path = path

    elif path == "/ws" or path.startswith("/ws/"):
        base = BACKEND
        backend_path = path

    else:
        base = FRONTEND
        backend_path = path

    target = base + backend_path

    if request.query_string:
        target += "?" + request.query_string

    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await proxy_websocket(request, target)

    headers = clean_headers(request.headers)

    try:
        async with ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target,
                headers=headers,
                data=await request.read(),
                allow_redirects=False
            ) as upstream:

                body = await upstream.read()
                response_headers = CIMultiDict()

                for key, value in upstream.headers.items():
                    if key.lower() not in HOP_HEADERS and key.lower() not in {
                        "content-length", "content-encoding"
                    }:
                        response_headers.add(key, value)

                return web.Response(
                    body=body,
                    status=upstream.status,
                    headers=response_headers
                )

    except Exception as error:
        print("HTTP proxy error:", error)

        return web.Response(
            text="Proxy error: " + str(error),
            status=502
        )


app = web.Application()
app.router.add_route("*", "/{path:.*}", handler)


if __name__ == "__main__":
    print("SATHACK reverse proxy running on port 9000")
    web.run_app(app, host="127.0.0.1", port=9000)
