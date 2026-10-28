import json

from app.core.config import settings


class UploadBodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/documents/upload"
        ):
            await self.app(scope, receive, send)
            return

        max_request_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 64 * 1024
        content_length = next(
            (
                value
                for key, value in scope.get("headers", [])
                if key.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > max_request_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_request_bytes:
                    raise UploadBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except UploadBodyTooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send):
        body = json.dumps({"detail": "Upload request exceeds the configured size limit."}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class UploadBodyTooLarge(Exception):
    pass
