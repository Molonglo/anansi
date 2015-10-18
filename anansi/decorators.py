import logging
import inspect
from functools import wraps,partial
from threading import Lock, Thread
from time import sleep

def locked_method(lock_name):
    def decorator(func):
        @wraps(func)
        def wrapped(self,*args,**kwargs):
            lock = self.__getattribute__(lock_name)
            lock.acquire()
            try:
                return func(self,*args,**kwargs)
            except Exception as error:
                raise error
            finally:
                lock.release()
        return wrapped
    return decorator

def serialised(func):
    serialised._lock = Lock()
    @wraps(func)
    def wrapped(*args,**kwargs):
        serialised._lock.acquire()
        try:
            retval = func(*args,**kwargs)
        except Exception as error:
            raise error
        finally:
            serialised._lock.release()
        return retval
    return wrapped

def try_and_log(*exceptions):
    def decorator(func):
        @wraps(func)
        def wrapped(*args,**kwargs):
            try:
                return func(*args,**kwargs)
            except exceptions as error:
                print error
        return wrapped
    return decorator

def retry(retries=5,wait=1,exception=Exception):
    def decorator(func):
        @wraps(func)
        def wrapped(*args,**kwargs):
            for _ in range(retries):
                try:
                    return func(*args,**kwargs)
                except exception as error:
                    sleep(wait)
            raise error
        return wrapped
    return decorator

def try_repr(i):
    try:
        return repr(i)
    except:
        return "<unknown>"

def log_args(func):
    @wraps(func)
    def wrapped(*args,**kwargs):
        args_str = ", ".join([try_repr(i) for i in args])
        kwargs_str = ", ".join(["%s=%s"%(a,try_repr(b)) for a,b in kwargs.items()])
        callstr = "%s(%s,%s)"%(func.__name__,args_str,kwargs_str)
        try:
            retval = func(*args,**kwargs)
        except Exception as error:
            msg = "Failed call: %s (%s)"%(callstr,str(error))
            logging.error(msg,exc_info=True)
            raise error
        else:
            msg = "%s -> %s"%(callstr,repr(retval))
            logging.debug(msg)
        return retval
    return wrapped

@serialised
@serialised
@serialised
@serialised
@serialised
@serialised
@serialised
@serialised
@retry(exception=ValueError)
def test():
    raise ValueError("I was called")

if __name__ == "__main__":
    logging.getLogger().setLevel(1)
    test()
    
