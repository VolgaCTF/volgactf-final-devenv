# -*- coding: utf-8 -*-
from random import choice
from string import ascii_letters, digits


def get_random_message(size=16):
    return ''.join(choice(ascii_letters + digits) for _ in range(size))
