import zstandard


class ZstdMiddleware:
    """Compress eligible non-streaming responses when the client supports zstd."""

    min_size = 1024

    def __init__(self, get_response):
        self.get_response = get_response
        self.compressor = zstandard.ZstdCompressor(level=3)

    def __call__(self, request):
        response = self.get_response(request)
        accepts_zstd = "zstd" in request.headers.get("Accept-Encoding", "").lower()
        content_type = response.headers.get("Content-Type", "").lower()

        if (
            accepts_zstd
            and not response.streaming
            and response.status_code not in (204, 304)
            and "Content-Encoding" not in response.headers
            and (
                content_type.startswith("text/")
                or "javascript" in content_type
                or "json" in content_type
                or "xml" in content_type
            )
        ):
            body = b"".join(response)
            if len(body) >= self.min_size:
                response.content = self.compressor.compress(body)
                response.headers["Content-Encoding"] = "zstd"
                response.headers.pop("Content-Length", None)
                response.headers["Vary"] = "Accept-Encoding"

        return response
