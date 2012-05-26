"""
Run with::

    uwsgi --file uwsgiapp.py --touch-reload uwsgiapp.py -p 10 --http-socket :8080 --max-request 1

Then go to localhost:8080
"""

from flask import Flask
application = Flask(__name__)
from flask import request
from contextlib import contextmanager, nested
from IPython.core.interactiveshell import InteractiveShell

@contextmanager
def capture():
    import sys
    from cStringIO import StringIO
    oldout,olderr = sys.stdout, sys.stderr
    try:
        out=[StringIO(), StringIO()]
        sys.stdout,sys.stderr = out
        yield out
    finally:
        sys.stdout,sys.stderr = oldout, olderr
        out[0] = out[0].getvalue()
        out[1] = out[1].getvalue()

@application.route('/')
def hello_world():
    # I replace \r\n with \n...this might cause problems for code that has legitimate \r characters in it
    # (like in a string)
    code = request.values.get('c','').replace('\r\n','\n')
    if len(code)>0:
        s="Code<br/><pre>%r</pre><hr/>"%code
        try:
            a=InteractiveShell()
            with capture() as out:
                a.run_cell(code)
#            c=compile(code,'<string>','exec')
#            with capture() as out:
#                exec c
            s+="Standard out<br/><pre>%s</pre><hr/>Standard Error<br/><pre>%s</pre>"%tuple(out)
        except Exception as e:
            s+="Error: %s"%e
        return s
    return "<form><textarea name='c' cols='100' rows='20'></textarea><br/><input type='submit'></form>"

if __name__ == '__main__':
    application.run()
