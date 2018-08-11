import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from aiohttp import web, ClientSession, BasicAuth
import os
import time
import json
import logging
import sys
import dateutil.parser
from dateutil.tz import tzlocal
from themis.finals.checker.result import Result
from datetime import datetime
import jwt

logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)


def import_path(filename):
    module = None
    directory, module_name = os.path.split(filename)
    module_name = os.path.splitext(module_name)[0]
    path = list(sys.path)
    sys.path.insert(0, directory)
    try:
        module = __import__(module_name)
    except Exception:
        logger.exception('An exception occurred', exc_info=sys.exc_info())
    finally:
        sys.path[:] = path  # restore
    return module


def load_checker():
    checker_module_name = os.getenv(
        'THEMIS_FINALS_CHECKER_MODULE',
        os.path.join(os.getcwd(), 'checker.py')
    )
    checker_module = import_path(checker_module_name)
    checker_push = getattr(checker_module, 'push')
    checker_pull = getattr(checker_module, 'pull')
    return checker_push, checker_pull


class CapsuleDecoder:
    def __init__(self):
        self.key = os.getenv(
            'THEMIS_FINALS_FLAG_SIGN_KEY_PUBLIC'
        ).replace('\\n', "\n")
        self.wrap_prefix_len = len(os.getenv('THEMIS_FINALS_FLAG_WRAP_PREFIX'))
        self.wrap_suffix_len = len(os.getenv('THEMIS_FINALS_FLAG_WRAP_SUFFIX'))

    def get_flag(self, capsule):
        payload = jwt.decode(
            capsule[self.wrap_prefix_len:-self.wrap_suffix_len],
            algorithms=['ES256', 'RS256'],
            key=self.key
        )
        return payload['flag']


class Metadata:
    def __init__(self, options):
        self._timestamp = options.get('timestamp', None)
        self._round = options.get('round', None)
        self._team_name = options.get('team_name', '')
        self._service_name = options.get('service_name', '')

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def round(self):
        return self._round

    @property
    def team_name(self):
        return self._team_name

    @property
    def service_name(self):
        return self._service_name


@web.middleware
async def basic_auth(request, handler):
    auth_header = request.headers.get('Authorization')
    authorized = False
    if auth_header:
        auth = BasicAuth.decode(auth_header)
        authorized = \
            auth.login == os.getenv('THEMIS_FINALS_AUTH_CHECKER_USERNAME') and\
            auth.password == os.getenv('THEMIS_FINALS_AUTH_CHECKER_PASSWORD')

    if not authorized:
        headers = {
            'WWW-Authenticate': 'Basic realm="{0}"'.format('Protected area')
        }
        return web.HTTPUnauthorized(headers=headers)

    return await handler(request)


class CheckerServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.loop = asyncio.get_event_loop()
        self.task_data = deque([])
        self.capsule_decoder = CapsuleDecoder()
        self.checker_push, self.checker_pull = load_checker()
        self.master_auth = BasicAuth(
            login=os.getenv('THEMIS_FINALS_AUTH_MASTER_USERNAME'),
            password=os.getenv('THEMIS_FINALS_AUTH_MASTER_PASSWORD')
        )

    async def internal_push(self, endpoint, capsule, label, metadata):
        result = Result.INTERNAL_ERROR
        updated_label = label
        message = None
        try:
            raw_result = await self.checker_push(endpoint, capsule, label,
                                                 metadata)
            if isinstance(raw_result, tuple):
                if len(raw_result) > 0:
                    result = raw_result[0]
                if len(raw_result) > 1:
                    updated_label = raw_result[1]
                if len(raw_result) > 2:
                    message = raw_result[2]
            else:
                result = raw_result
        except Exception:
            logger.error('An exception occured', exc_info=sys.exc_info())
        return result, updated_label, message

    async def internal_pull(self, endpoint, capsule, label, metadata):
        result = Result.INTERNAL_ERROR
        message = None
        try:
            raw_result = await self.checker_pull(endpoint, capsule, label,
                                                 metadata)
            if isinstance(raw_result, tuple):
                if len(raw_result) > 0:
                    result = raw_result[0]
                if len(raw_result) > 1:
                    message = raw_result[1]
            else:
                result = raw_result
        except Exception:
            logger.exception('An exception occurred', exc_info=sys.exc_info())
        return result, message

    async def background_push(self, payload):
        params = payload['params']
        metadata = Metadata(payload['metadata'])
        t_created = dateutil.parser.parse(metadata.timestamp)
        t_delivered = datetime.now(tzlocal())

        flag = self.capsule_decoder.get_flag(params['capsule'])

        status, updated_label, message = await self.internal_push(
            params['endpoint'],
            params['capsule'],
            params['label'],
            metadata
        )

        t_processed = datetime.now(tzlocal())

        job_result = dict(
            status=status.value,
            flag=flag,
            label=updated_label,
            message=message
        )

        delivery_time = (t_delivered - t_created).total_seconds()
        processing_time = (
            t_processed - t_delivered
        ).total_seconds()

        log_message = ('PUSH flag `{0}` /{1:d} to `{2}`@`{3}` ({4}) - '
                       'status {5}, label `{6}` [delivery {7:.2f}s, '
                       'processing {8:.2f}s]').format(
            flag,
            metadata.round,
            metadata.service_name,
            metadata.team_name,
            params['endpoint'],
            status.name,
            job_result['label'],
            delivery_time,
            processing_time
        )

        logger.info(log_message)

        async with ClientSession(auth=self.master_auth) as session:
            uri = payload['report_url']
            async with session.post(uri, json=job_result) as r:
                if r.status != 204:
                    logger.error(r.status)
                    logger.error(await r.text())

    async def background_pull(self, payload):
        params = payload['params']
        metadata = Metadata(payload['metadata'])
        t_created = dateutil.parser.parse(metadata.timestamp)
        t_delivered = datetime.now(tzlocal())

        flag = self.capsule_decoder.get_flag(params['capsule'])

        status, message = await self.internal_pull(
            params['endpoint'],
            params['capsule'],
            params['label'],
            metadata
        )

        t_processed = datetime.now(tzlocal())

        job_result = dict(
            request_id=params['request_id'],
            status=status.value,
            message=message
        )

        delivery_time = (t_delivered - t_created).total_seconds()
        processing_time = (
            t_processed - t_delivered
        ).total_seconds()

        log_message = ('PULL flag `{0}` /{1:d} from `{2}`@`{3}` ({4}) with '
                       'label `{5}` - status {6} [delivery {7:.2f}s, '
                       'processing {8:.2f}s]').format(
            flag,
            metadata.round,
            metadata.service_name,
            metadata.team_name,
            params['endpoint'],
            params['label'],
            status.name,
            delivery_time,
            processing_time
        )

        logger.info(log_message)

        async with ClientSession(auth=self.master_auth) as session:
            uri = payload['report_url']
            async with session.post(uri, json=job_result) as r:
                if r.status != 204:
                    logger.error(r.status)
                    logger.error(await r.text())

    async def process_queue(self):
        while True:
            if self.task_data:
                entry = self.task_data.popleft()
                task_type = entry['type']
                payload = entry['payload']
                try:
                    if task_type == 'push':
                        await self.background_push(payload)
                    elif task_type == 'pull':
                        await self.background_pull(payload)
                except Exception:
                    logger.error('Caught an exception',
                                 exc_info=sys.exc_info())
            else:
                await asyncio.sleep(0.1)

    async def start_background_tasks(self, app):
        app['dispatch'] = app.loop.create_task(self.process_queue())

    async def cleanup_background_tasks(self, app):
        app['dispatch'].cancel()
        await app['dispatch']

    async def safe_json_payload(self, request):
        payload = None
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            logger.error('Invalid payload', exc_info=sys.exc_info())
        finally:
            return payload

    def enqueue_task(self, task_type, payload):
        self.task_data.append(dict(
            type=task_type,
            payload=payload
        ))

    async def handle_push(self, request):
        payload = await self.safe_json_payload(request)
        if payload is None:
            return web.Response(status=400)
        self.enqueue_task('push', payload)
        return web.Response(status=202)

    async def handle_pull(self, request):
        payload = await self.safe_json_payload(request)
        if payload is None:
            return web.Response(status=400)
        self.enqueue_task('pull', payload)
        return web.Response(status=202)

    def get_routes(self):
        return [
            web.post('/push', self.handle_push),
            web.post('/pull', self.handle_pull)
        ]

    async def create_app(self):
        app = web.Application(middlewares=[basic_auth])
        app.add_routes(self.get_routes())
        return app

    def run_app(self):
        loop = self.loop
        app = loop.run_until_complete(self.create_app())
        app.on_startup.append(self.start_background_tasks)
        app.on_cleanup.append(self.cleanup_background_tasks)
        web.run_app(app, host=self.host, port=self.port)


if __name__ == '__main__':
    checker = CheckerServer(host='0.0.0.0', port=80)
    checker.run_app()
