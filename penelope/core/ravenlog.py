from raven.middleware import Sentry
from raven.base import Client
from raven.utils.wsgi import get_current_url, get_headers, get_environ


class PenelopeSentry(Sentry):

    def cleanup_headers(self, headers):
        if 'Cookie' in headers:
            del headers['Cookie']
        return headers

    def handle_exception(self, environ):
        event_id = self.client.captureException(
            data={
                'sentry.interfaces.Http': {
                    'method': environ.get('REQUEST_METHOD'),
                    'url': get_current_url(environ, strip_querystring=True),
                    'query_string': environ.get('QUERY_STRING'),
                    'headers': self.cleanup_headers(dict(get_headers(environ))),
                    'env': dict(get_environ(environ)),
                }
            },
        )
        return event_id


def sentry_filter_factory(app, global_conf, **kwargs):
    client = Client(**kwargs)
    return PenelopeSentry(app, client)
