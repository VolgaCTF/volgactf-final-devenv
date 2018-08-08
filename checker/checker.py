# -*- coding: utf-8 -*-
from time import sleep
from random import randrange
from themis.finals.checker.result import Result
import logging
from external import get_random_message

logger = logging.getLogger(__name__)


async def push(endpoint, capsule, label, metadata):
    delay = randrange(1, 5)
    logger.debug('Sleeping for {0} seconds...'.format(delay))
    sleep(delay)
    return Result.UP, label, get_random_message()


async def pull(endpoint, capsule, label, metadata):
    delay = randrange(1, 5)
    logger.debug('Sleeping for {0} seconds...'.format(delay))
    sleep(delay)
    return Result.UP, get_random_message()
