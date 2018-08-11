# -*- coding: utf-8 -*-
from time import sleep
from random import randrange
from themis.finals.checker.result import Result
import logging
from external import get_random_message
from aiohttp import ClientSession
import sys

logger = logging.getLogger(__name__)


async def ping_service(endpoint):
    async with ClientSession() as session:
        uri = 'http://{0}:{1:d}'.format(endpoint, 8080)
        try:
            async with session.head(uri) as r:
                return r.status == 200
        except Exception:
            logger.error('An exception occured', exc_info=sys.exc_info())
            return False


async def push(endpoint, capsule, label, metadata):
    delay = randrange(1, 5)
    logger.debug('Sleeping for {0} seconds...'.format(delay))
    sleep(delay)
    if not await ping_service(endpoint):
        return Result.DOWN
    new_label = get_random_message(8)
    return Result.UP, new_label, get_random_message()


async def pull(endpoint, capsule, label, metadata):
    delay = randrange(1, 5)
    logger.debug('Sleeping for {0} seconds...'.format(delay))
    sleep(delay)
    if not await ping_service(endpoint):
        return Result.DOWN
    return Result.UP, get_random_message()
