import jsonrpc.proxy

from pyramid import testing
from webtest import TestApp

from penelope.core.models.dashboard import User, Project, Group

User.__mapper__.order_by = []
Project.manager.property.order_by = []
Group.users.property.order_by = []


def setUp(test, *args, **kwargs):
    testing.setUp()

def tearDown(test):
    testing.tearDown()

def Test_RPC_App(**kwargs):
    from penelope.core import main
    settings = {'test': True,
                'sa.dashboard.url': 'sqlite://',
                'velruse.openid.store':'openid.store.memstore.MemoryStore',
                'velruse.openid.realm':'localhost',
                }
    app = main({}, **settings)
    return TestApp(app, **kwargs)

app = Test_RPC_App()

def fakepost(self, url, data):
    if url.endswith('/'):
        url = url[:-1]
    respdata = app.post(url, data)
    respdata.read = lambda : respdata.body
    return respdata

jsonrpc.proxy.JSONRPCProxy._post = fakepost
