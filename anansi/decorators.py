import logging
import inspect

def try_and_log(*exceptions):
    def decorator(func):
        def wrapped(*args,**kwargs):
            try:
                return func(*args,**kwargs)
            except exceptions as error:
                print error
        return wrapped
    return decorator

def try_repr(i):
    try:
        return repr(i)
    except:
        return "<unknown>"

def log_args(func):
    def wrapped(*args,**kwargs):
        args_str = ", ".join([try_repr(i) for i in args])
        kwargs_str = ", ".join(["%s=%s"%(a,try_repr(b)) for a,b in kwargs.items()])
        callstr = "%s(%s,%s)"%(func.__name__,args_str,kwargs_str)
        try:
            retval = func(*args,**kwargs)
        except Exception as error:
            msg = "Failed call: %s (%s)"%(callstr,str(error))
            logging.error(msg)
            raise error
        else:
            msg = "%s -> %s"%(callstr,repr(retval))
            logging.debug(msg)
        return retval
    return wrapped


