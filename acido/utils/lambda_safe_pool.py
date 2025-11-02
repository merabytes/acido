# lambda_safe_pool.py
from concurrent.futures import ThreadPoolExecutor

class AsyncResultShim:
    """
    Minimal wrapper to mimic multiprocessing.AsyncResult used by your code.
    - wait(): blocks until done, returns None (matches multiprocessing semantics)
    - get(timeout=None): returns result (or raises)
    - ready(): True if done
    - successful(): True if done and no exception
    """
    def __init__(self, fut):
        self._fut = fut

    def wait(self, timeout=None):
        self._fut.result(timeout=timeout)  # block; discard result to match .wait() behavior
        return None

    def get(self, timeout=None):
        return self._fut.result(timeout=timeout)

    def ready(self):
        return self._fut.done()

    def successful(self):
        if not self._fut.done():
            return False
        return self._fut.exception() is None

class ThreadPoolShim:
    """
    A safe stand-in for multiprocessing.pool.ThreadPool using ThreadPoolExecutor.
    Provides map, imap_unordered, and apply_async (with callback) APIs.
    """
    def __init__(self, processes: int = None, max_workers: int = None):
        self._executor = ThreadPoolExecutor(max_workers=max_workers or processes or 1)

    def map(self, fn, iterable, chunksize=1):
        # chunksize ignored; semantics close enough for typical uses
        return self._executor.map(fn, iterable)

    def imap_unordered(self, fn, iterable, chunksize=1):
        # Keep orderless completion
        futures = [self._executor.submit(fn, item) for item in iterable]
        for fut in futures:
            # consume as they finish by polling; or use as_completed if you prefer
            pass
        from concurrent.futures import as_completed
        for fut in as_completed(futures):
            yield fut.result()

    def apply_async(self, fn, args=(), kwds=None, callback=None):
        kwds = kwds or {}
        fut = self._executor.submit(fn, *args, **kwds)

        if callback is not None:
            def _cb(done_future):
                try:
                    res = done_future.result()
                except Exception as e:
                    res = e  # preserve behavior: callback receives exception object
                try:
                    callback(res)
                except Exception:
                    # swallow callback exceptions like multiprocessing does
                    pass
            fut.add_done_callback(_cb)

        return AsyncResultShim(fut)

    # Lifecycle methods to mimic multiprocessing.Pool
    def close(self):
        pass  # no-op

    def terminate(self):
        self._executor.shutdown(wait=False, cancel_futures=True)

    def join(self):
        self._executor.shutdown(wait=True)

