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

def split_file(input_file, number_of_containers):
    number_of_lines = len([line.strip() for line in open(input_file, 'r').readlines()])
    chunked_lines = int(number_of_lines / number_of_containers)
    print(good(f'Splitting into {number_of_containers} files.'))
    os.system(f'split -l {str(chunked_lines)} {input_file} /tmp/acido-input-')

    directory = os.fsencode('/tmp/')
    input_files = []
        
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.startswith("acido-input"): 
            input_files.append(f'/tmp/{filename}')
        else:
            continue

    return input_files