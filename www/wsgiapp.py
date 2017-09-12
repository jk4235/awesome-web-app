import logging; logging.basicConfig(level=logging.INFO)
import os
import datetime, time

from transwarp import db
from  transwarp.web import WSGIApplication, Jinja2TemplateEngine

from configs import configs


db.create_engine(**configs.db)

wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'a minute ago'
    if delta < 3600:
        return u'%s minutes ago' % (delta // 60)
    if delta < 86400:
        return u'%s hours ago' % (delta // 3600) if (delta // 3600) > 1 else '1 hour ago'
    if delta < 604800:
        return u'%s days ago' % (delta // 86400) if (delta // 86400) > 1 else '1 day ago'
    dt = datetime.fromtimestamp(t)
    return '%s/%s/%s' % (dt.year, dt.month, dt.day)

template_engine = Jinja2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
template_engine.add_filter('datetime', datetime_filter)
wsgi.template_engine = template_engine

import urls
wsgi.add_module(urls)

if __name__ == '__main__':
    wsgi.run(9000)
