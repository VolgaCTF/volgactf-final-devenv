import asyncio
from aiohttp import web


class ServiceServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.loop = asyncio.get_event_loop()

    async def handle(self, request):
        return web.Response(text='OK')

    async def create_app(self):
        app = web.Application()
        app.add_routes([web.get('/', self.handle)])
        return app

    def run_app(self):
        loop = self.loop
        app = loop.run_until_complete(self.create_app())
        web.run_app(app, host=self.host, port=self.port)


if __name__ == '__main__':
    service = ServiceServer(host='0.0.0.0', port=8080)
    service.run_app()
