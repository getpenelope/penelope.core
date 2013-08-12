from velruse.providers import google
from velruse.exceptions import ThirdPartyFailure
from velruse.exceptions import AuthenticationDenied
from pyramid.httpexceptions import HTTPFound


def includeme(config):
    settings = config.registry.settings
    store, realm = setup_openid(config)
    consumer = RedturtleConsumer(
        storage=store,
        realm=realm,
        process_url='redturtle_process',
        oauth_key=settings.get('velruse.google.consumer_key'),
        oauth_secret=settings.get('velruse.google.consumer_secret'),
        request_attributes=settings.get('request_attributes')
    )
    config.add_route("redturtle_login", "/redturtle/login")
    config.add_route("redturtle_process", "/redturtle/process",
                     use_global_views=True,
                     factory=consumer.process)
    config.add_view(consumer.login, route_name="redturtle_login", request_method="POST")


def setup_openid(config):
    settings = config.registry.settings
    store = getattr(config.registry,'velruse.openid_store', None)
    if not store and 'velruse.openid.store' not in settings:
        raise Exception("Missing 'velruse.openid.store' in config settings.")
    if not store:
        store = config.maybe_dotted(settings['velruse.openid.store'])()
        setattr(config.registry,'velruse.openid_store',store)
    realm = settings['velruse.openid.realm']
    return store, realm


class RedturtleConsumer(google.GoogleConsumer):

    def _lookup_identifier(self, request, identifier):
        """Return the Google OpenID directed endpoint"""
        domain = request.registry.settings.get('penelope.core.google_domain')
        return "https://www.google.com/accounts/o8/site-xrds?hd=%s" % domain

    def login(self, context, request):
        return super(RedturtleConsumer, self).login(request)

    def process(self, request):
        try:
            return super(RedturtleConsumer, self).process(request)
        except ThirdPartyFailure:
            raise HTTPFound(location='/')
        except AuthenticationDenied:
            request.add_message('Authentication from google has failed. Try again.', 'error')
            raise HTTPFound(location='/')
