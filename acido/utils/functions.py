from huepy import *
import time
import subprocess
import os
from os.path import join as jpath
from os.path import expanduser
from base64 import b64encode, b64decode

def basic_auth_header(password):
    user_pass = f':{password}'
    basic_credentials = b64encode(user_pass.encode()).decode()
    return basic_credentials

def chunks(iterable, chunk_size):
    """Generates lists of `chunk_size` elements from `iterable`.
    >>> list(chunk((2, 3, 5, 7), 3))
    [[2, 3, 5], [7]]
    >>> list(chunk((2, 3, 5, 7), 2))
    [[2, 3], [5, 7]]
    """
    iterable = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(chunk_size):
                chunk.append(next(iterable))
            yield chunk
        except StopIteration:
            if chunk:
                yield chunk
            break
