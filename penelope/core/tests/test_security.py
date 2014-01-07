import unittest2

from sqlalchemy import engine_from_config
from sqlalchemy.orm import sessionmaker
from pyramid.httpexceptions import HTTPForbidden, HTTPFound
from pyramid import testing
from pyramid.threadlocal import get_current_registry
from pyramid.interfaces import IAuthorizationPolicy, IAuthenticationPolicy
from pyramid.authentication import RepozeWho1AuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from webtest import TestApp
from mock import patch

from penelope.core.models.dashboard import User
from penelope.core.models import Base, Project, Customer, Role, Group, CustomerRequest, Application, TimeEntry
from penelope.core import main
from penelope.core.views import PORRequest

settings = {'test': True,
            'sa.dashboard.url': 'sqlite://',
            'sa.dashboard.echo': False,
            'cache.regions' : 'calculate_matrix, template_caching, default_term',
            'cache.type' : 'memory',
            'cache.calculate_matrix.expire' : '0',
            'project_name': 'Penelope',
            'velruse.openid.store':'openid.store.memstore.MemoryStore',
            'velruse.openid.realm':'localhost',}

def dummy_forbidden(request):
    return HTTPForbidden()


from penelope.core.security import views
views.forbidden = dummy_forbidden

class BaseTestCase(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = engine_from_config(settings, prefix='sa.dashboard.')
        cls.Session = sessionmaker()

        #populate basic stuff
        Base.metadata.bind = cls.engine
        Base.metadata.create_all(cls.engine)

        import penelope.core.models
        class MockSession(cls.Session):
            def __call__(self):
                return self
        penelope.core.models.DBSession = MockSession(bind=cls.engine)

    def setUp(self):
        from formalchemy.forms import FieldSet
        self.original_validate = FieldSet.validate
        self.original_sync = FieldSet.sync
        FieldSet.validate = lambda x: True
        FieldSet.sync = lambda x: True

        from pyramid_formalchemy.views import ModelView
        self.original_delete = ModelView.delete
        ModelView.delete = lambda x: HTTPFound(location='/')

        connection = self.engine.connect()

        # begin a non-ORM transaction
        self.trans = connection.begin()

        # bind an individual Session to the connection
        self.session = self.Session(bind=connection)
        Base.session = self.Session

        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

        #Moneky patch for testing
        from penelope.core.reports import queries
        self.original_qry_active_projects = queries.qry_active_projects
        queries.qry_active_projects = lambda: self.session.query(Project).filter_by(id='not existing id')

        user = User(email=u'u1@rt.com')
        self.session.add(user)

        customer = Customer(name=u'My Customer')
        self.session.add(customer)

        project = Project(name=u'My Project')
        cr = CustomerRequest(name=u"My CR", id="my-project_1")
        project.add_customer_request(cr)

        customer.add_project(project)
        self.session.add(project)

        self.session.commit()

    def tearDown(self):
        # rollback - everything that happened with the
        # Session above (including calls to commit())
        # is rolled back.
        testing.tearDown()
        self.trans.rollback()
        self.session.close()

        from penelope.core.reports import queries
        queries.qry_active_projects = self.original_qry_active_projects

        from formalchemy.forms import FieldSet
        FieldSet.validate = self.original_validate
        FieldSet.sync = self.original_sync

        from pyramid_formalchemy.views import ModelView
        ModelView.delete = self.original_delete


class IntegrationTestBase(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        super(IntegrationTestBase, cls).setUpClass()
        cls.app = main({}, **settings)

    def authenticate_as(self, roles=None, user_id=None):
        if not user_id:
            self.user = self.session.query(User).filter_by(email=u'u1@rt.com').one()
        else:
            self.user = self.session.query(User).get(user_id)
        if roles:
            self.user.roles_in_context = lambda x: set(roles)
        normal_get = self.app.get
        normal_post = self.app.post

        def authenticated_get(*args, **kwargs):
            kwargs['expect_errors'] = True
            kwargs['extra_environ'] = {'repoze.who.identity': {'user': self.user,
                                       'repoze.who.userid': self.user.id}}
            return normal_get(*args, **kwargs)

        def authenticated_post(*args, **kwargs):
            kwargs['expect_errors'] = True
            kwargs['extra_environ'] = {'repoze.who.identity': {'user': self.user,
                                       'repoze.who.userid': self.user.id}}
            return normal_post(*args, **kwargs)

        self.app.get = authenticated_get
        self.app.post = authenticated_post

    def setUp(self):
        self.app = TestApp(self.app)
        self.config = testing.setUp()
        super(IntegrationTestBase, self).setUp()


class TestQuerySecurity(IntegrationTestBase):

    def setUp(self):
        self.config = testing.setUp()
        super(TestQuerySecurity, self).setUp()
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        import penelope.core.models
        self.session = penelope.core.models.DBSession()

    def tearDown(self):
        testing.tearDown()
        super(TestQuerySecurity, self).tearDown()

    def _add_policy(self, user):
        from penelope.core import security
        authentication_policy = RepozeWho1AuthenticationPolicy(callback=security.rolefinder)
        authorization_policy = ACLAuthorizationPolicy()
        registry = get_current_registry()
        registry.registerUtility(authorization_policy, IAuthorizationPolicy)
        registry.registerUtility(authentication_policy, IAuthenticationPolicy)
        environ = {'repoze.who.identity': {'user': user,
                   'repoze.who.userid': user.id}}

        from penelope.core.security import acl
        registry.registerAdapter(acl.GenericRoles, (acl.Interface, acl.IUser),
                                 acl.IRoleFinder)
        registry.registerAdapter(acl.ProjectRelatedRoles, (acl.IProjectRelated, acl.IUser),
                                 acl.IRoleFinder)
        registry.registerAdapter(acl.CustomerRelatedRoles, (acl.ICustomer, acl.IUser),
                                 acl.IRoleFinder)
        registry.registerAdapter(acl.UserRoles, (acl.IUser, acl.IUser),
                                 acl.IRoleFinder)

        return PORRequest.blank('/foo', environ=environ)

    def test_empty_security_listing(self):
        user = User(email=u'u1@rt.com')
        self.session.add(user)
        project = Project(name=u'My Project 1')
        self.session.add(project)
        self.session.commit()

        query = self.session.query(Project)
        request = self._add_policy(user)
        filtered_projects = request.filter_viewables(query)
        self.assertEqual(tuple(filtered_projects),())

    def test_security_listing(self):
        user = User(email=u'u2@rt.com')
        self.session.add(user)
        project = Project(name=u'My Project 2')
        self.session.add(project)
        self.session.commit()

        query = self.session.query(Project)
        role = Role(name=u'internal_developer')
        user.roles.append(role)
        group = Group()
        group.roles.append(role)
        group.users.append(user)
        project = query.get('my-project-2')
        project.add_group(group)
        self.session.commit()

        request = self._add_policy(user)
        filtered_projects = request.filter_viewables(query)
        self.assertEqual(len(tuple(filtered_projects)), 1)

    def test_security_listing_with_empties(self):
        user = User(email=u'u3@rt.com')
        self.session.add(user)
        project = Project(name=u'My Project 3')
        self.session.add(project)
        self.session.commit()

        query = self.session.query(Project)

        project2 = Project(name=u'My Project 4')
        self.session.add(project2)

        role = Role(name=u'internal_developer')
        user.roles.append(role)
        group = Group()
        group.roles.append(role)
        group.users.append(user)
        project = query.get('my-project-3')
        project.add_group(group)
        self.session.commit()

        request = self._add_policy(user)
        filtered_projects = request.filter_viewables(query)
        self.assertEqual(len(tuple(filtered_projects)), 1)

    def test_security_listing_global_roles(self):
        user = User(email=u'u4@rt.com')
        self.session.add(user)
        project = Project(name=u'My Project 5')
        self.session.add(project)
        self.session.commit()

        query = self.session.query(Project)

        project2 = Project(name=u'My Project 6')
        self.session.add(project2)

        role = Role(name=u'project_manager')
        user.roles.append(role)
        self.session.commit()

        request = self._add_policy(user)
        filtered_projects = request.filter_viewables(query)
        self.assertEqual(len(tuple(filtered_projects)), 2)

    def test_roles_in_context(self):
        user = User(email=u'roles_matrix')
        internal_developer = Role(name=u'internal_developer')
        user.roles.append(internal_developer)

        self.session.add(user)

        project = Project(name=u'p1_for_roles_matrix')
        external_developer = Role(name=u'external_developer')
        a_role = Role(name=u'a role')
        p1_group_2 = Group(project=project)
        p1_group_2.roles.append(a_role)
        p1_group = Group(project=project)
        p1_group.add_user(user)
        p1_group.roles.append(external_developer)

        self.session.add(project)
        self.session.commit()

        from penelope.core.security import acl
        self.assertItemsEqual(acl.GenericRoles(project, user).get_roles(), set(['internal_developer']))
        self.assertItemsEqual(acl.GenericRoles(None, user).get_roles(), set(['internal_developer']))
        self.assertTrue('internal_developer' not in acl.ProjectRelatedRoles(project, user).get_roles())
        self.assertTrue('external_developer' in acl.ProjectRelatedRoles(project, user).get_roles())
        self.assertTrue('owner' in acl.UserRoles(user, user).get_roles())
        self.assertTrue('internal_developer' in acl.UserRoles(user, user).get_roles())

    def test_project_manager_in_context(self):
        user = User(email=u'roles_matrix')
        self.session.add(user)

        project = Project(name=u'p1_for_roles_matrix')
        cr = CustomerRequest(name=u"My CR", id="my-p1_for_roles_matrix")
        project.add_customer_request(cr)
        pm = Role(name=u'project_manager')
        p1_group = Group(project=project)
        p1_group.add_user(user)
        p1_group.roles.append(pm)

        self.session.add(project)
        self.session.commit()

        from penelope.core.security import acl
        self.assertTrue('project_manager' in acl.ProjectRelatedRoles(project, user).get_roles())


TestQuerySecurity.setUpClass()


class SecurityLocalRolesMatrixTest(IntegrationTestBase):

    def setUp(self):
        super(SecurityLocalRolesMatrixTest, self).setUp()

        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

        import penelope.core.models
        self.session = penelope.core.models.DBSession()

        user = User(email=u'u1@rt.com')
        self.session.add(user)

        customer = Customer(name=u'My Customer')
        self.session.add(customer)

        project = Project(name=u'My Project')
        cr = CustomerRequest(name=u"My CR", id="my-project_1")
        project.add_customer_request(cr)
        customer.add_project(project)
        self.session.add(project)
        self.session.commit()

    def test_customer_view_for_local_roles(self):
        from penelope.core.models import DBSession
        path = '/admin/Customer/my-customer'
        old = Project.active
        Project.active = Project.activated==True

        #internal_developer
        role = Role(name=u'internal_developer')
        user = DBSession.query(User).get(1)
        user.roles.append(role)
        self.session.commit()

        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=403)
        self.assertEqual(403, res.status_int, msg="For %s %s - got %s - should have 403" % (path, user, res.status_int))

        group = Group()
        group.roles.append(role)
        group.users.append(user)
        project = DBSession.query(Project).get('my-project')
        project.add_group(group)
        self.session.commit()

        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=200)
        self.assertEqual(200, res.status_int, msg="For %s %s - got %s - should have 200" % (path, user, res.status_int))

        #external_developer
        group.project_id = None
        role.id = u'external_developer'
        self.session.commit()

        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=403)
        #self.assertEqual(403, res.status_int, msg="For %s %s - got %s - should have 403" % (path, user, res.status_int))

        group.roles.append(role)
        project.add_group(group)
        self.session.commit()
        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=200)
        self.assertEqual(200, res.status_int, msg="For %s %s - got %s - should have 200" % (path, user, res.status_int))

        #customer
        group.project_id = None
        role.id = u'customer'
        self.session.commit()

        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=403)
        #self.assertEqual(403, res.status_int, msg="For %s %s - got %s - should have 403" % (path, user, res.status_int))

        group.roles.append(role)
        project.add_group(group)
        self.session.commit()
        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=200)
        self.assertEqual(200, res.status_int, msg="For %s %s - got %s - should have 200" % (path, user, res.status_int))

        #wrong role
        group.project_id = None
        role.id = u'stupid_name'
        self.session.commit()

        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=403)
        #self.assertEqual(403, res.status_int, msg="For %s %s - got %s - should have 403" % (path, user, res.status_int))

        group.roles.append(role)
        project.add_group(group)
        self.session.commit()
        self.authenticate_as(user_id=1)
        res = self.app.get(path, status=403)
        #self.assertEqual(403, res.status_int, msg="For %s %s - got %s - should have 403" % (path, user, res.status_int))

        Project.active = old


        #
        # test that user cannot see projects listed in dashboard without a 'view' permission
        #

        # authenticated, no local roles
        user = User(email=u'u9@rt.com')
        self.session.add(user)

        project = Project(name=u'My Project 9')
        self.session.add(project)
        self.session.commit()

        self.authenticate_as(user_id=user.id)

        res = self.app.get('/')
        self.assertNotIn(project.name, res.ubody)

        role = Role(name=u'customer')
        group = Group()
        group.roles.append(role)
        group.users.append(user)

        self.session.commit()

        res = self.app.get('/')
        self.assertNotIn(project.name, res.ubody)


SecurityLocalRolesMatrixTest.setUpClass()


class SecurityMatrixTest(IntegrationTestBase):

    def por_security_matrix(self, path, matrix, POST=False):
        for roles, status in matrix:
            self.authenticate_as(roles=roles)
            if POST: res = self.app.post(path, status=status)
            else: res = self.app.get(path, status=status)
            self.assertEqual(status, res.status_int, msg="For %s %s - got %s - should have %s" % (path, roles, res.status_int, status))

    def por_anonymous(self, path, status, POST=False):
        if POST: res = self.app.post(path, status=status)
        else: res = self.app.get(path, status=status)
        self.assertEqual(status, res.status_int, msg="For %s (Anonymous) - got %s - should have %s" % (path, res.status_int, status))

    def test_root(self):
        path = '/'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      200),
                                        (('owner',),              200),
                                        (('customer',),           200),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                      ])

    def test_login_forms(self):
        self.por_anonymous('/login_form', 200)
        self.por_anonymous('/login_success', 302)
        self.por_anonymous('/change_password', 404)
        self.por_anonymous('/change_password?token=', 200)
        self.por_anonymous('/password_reset_form', 200)
        self.por_anonymous('/password_reset', 200, POST=True)
        self.por_anonymous('/logout', 302)

    def test_view_iterations(self):
        path = '/view_iterations'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_manage_iterations(self):
        path = '/manage_iterations'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_generate_iterations(self):
        path = '/generate_iteration'
        self.por_anonymous(path, 403, POST=True)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          302),
                                        (('project_manager',),    302),
                                        (('administrator',),      302),
                                       ], POST=True)

    def test_add_time_entry(self):
        path = '/add_entry'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_my_entries(self):
        path = '/reports/report_my_entries'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_reports_index(self):
        path = '/reports/index'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_reports_all_entries(self):
        path = '/reports/report_all_entries'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_reports_state_change(self):
        path = '/reports/report_state_change'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_reports_custom(self):
        path = '/reports/report_custom'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_user_listing(self):
        path = '/admin/User'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('administrator',),      200),
                                       ])

    def test_user_view(self):
        user_id = self.session.query(User.id).filter_by(email=u'u1@rt.com').one()
        path = '/admin/User/%s' % user_id
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              200),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])

    def test_user_tokens(self):
        user_id = self.session.query(User.id).filter_by(email=u'u1@rt.com').one()
        path = '/admin/User/%s/user_tokens' % user_id
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              200),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])

    def test_user_edit(self):
        user_id = self.session.query(User.id).filter_by(email=u'u1@rt.com').one()
        path = '/admin/User/%s/edit' % user_id
        self.por_anonymous(path, 403)
        self.por_anonymous(path, 403, POST=True)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              200),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              302),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      302),
                                       ], POST=True)

#    def test_user_delete(self):
#        user_id = self.session.query(User.id).filter_by(email=u'u1@rt.com').one()
#        path = '/admin/User/%s/delete' % user_id
#        self.por_anonymous(path, 403, POST=True)
#        self.por_security_matrix(path, [(('authenticated',),      403),
#                                        (('owner',),              403),
#                                        (('customer',),           403),
#                                        (('external_developer',), 403),
#                                        (('internal_developer',), 403),
#                                        (('secretary',),          403),
#                                        (('project_manager',),    403),
#                                       ], POST=True)

    def test_role_listing(self):
        path = '/admin/Role'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])

    def test_role_add(self):
        path = '/admin/Role/new'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])

    def test_role_edit(self):
        role = Role(name=u'old_role')
        self.session.add(role)
        self.session.commit()
        path = '/admin/Role/old_role/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    403),
                                        (('administrator',),      200),
                                       ])

#    def test_role_delete(self):
#        role = Role(name='to_be_deleted')
#        self.session.add(role)
#        self.session.commit()
#        path = '/admin/Role/to_be_deleted/delete'
#        self.por_anonymous(path, 403, POST=True)
#        self.por_security_matrix(path, [(('authenticated',),      403),
#                                        (('owner',),              403),
#                                        (('customer',),           403),
#                                        (('external_developer',), 403),
#                                        (('internal_developer',), 403),
#                                        (('secretary',),          403),
#                                        (('project_manager',),    403),
#                                        (('administrator',),      302),
#                                       ], POST=True)

    def test_customers_list(self):
        path = '/admin/Customer'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      200),
                                        (('owner',),              200),
                                        (('customer',),           200),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customers_add(self):
        path = '/admin/Customer/new'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customer_view(self):
        path = '/admin/Customer/my-customer'
        old = Project.active
        Project.active = Project.activated==True
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           200),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])
        Project.active = old

    def test_customer_metadata(self):
        path = '/admin/Customer/my-customer/metadata'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           200),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customer_edit(self):
        path = '/admin/Customer/my-customer/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

#    def test_customer_delete(self):
#        customer = Customer(name=u'To Be Deleted Customer')
#        self.session.add(customer)
#        self.session.commit()
#        path = '/admin/Customer/to-be-deleted-customer/delete'
#        self.por_anonymous(path, 403, POST=True)
#        self.por_security_matrix(path, [(('authenticated',),      403),
#                                        (('owner',),              403),
#                                        (('customer',),           403),
#                                        (('external_developer',), 403),
#                                        (('internal_developer',), 403),
#                                        (('secretary',),          403),
#                                        (('project_manager',),    302),
#                                        (('administrator',),      302),
#                                       ], POST=True)

    def test_customer_time_entries(self):
        path = '/admin/Customer/my-customer/customer_time_entries?customer_id=my-customer'
        old = Project.active
        Project.active = Project.activated==True
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])
        Project.active = old

    def test_customer_add_project(self):
        path = '/admin/Customer/my-customer/add_project'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_list(self):
        path = '/admin/Project'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      200),
                                        (('owner',),              200),
                                        (('customer',),           200),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_view(self):
        path = '/admin/Project/my-project'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           302),
                                        (('external_developer',), 302),
                                        (('internal_developer',), 302),
                                        (('secretary',),          302),
                                        (('project_manager',),    302),
                                        (('administrator',),      302),
                                       ])

    def test_project_metadata(self):
        path = '/admin/Project/my-project/metadata'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_edit(self):
        path = '/admin/Project/my-project/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_configuration(self):
        path = '/admin/Project/my-project/configuration'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_add_group(self):
        path = '/admin/Project/my-project/add_group'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_add_app(self):
        path = '/admin/Project/my-project/add_application'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_project_config_apps(self):
        path = '/admin/Project/my-project/applications'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           200),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

#    def test_project_delete(self):
#        prj = Project(name=u'To Be Deleted')
#        self.session.add(prj)
#        self.session.commit()
#        path = '/admin/Project/to-be-deleted/delete'
#        self.por_anonymous(path, 403, POST=True)
#        self.por_security_matrix(path, [(('authenticated',),      403),
#                                        (('owner',),              403),
#                                        (('customer',),           403),
#                                        (('external_developer',), 403),
#                                        (('internal_developer',), 403),
#                                        (('secretary',),          403),
#                                        (('project_manager',),    302),
#                                        (('administrator',),      302),
#                                       ], POST=True)


    def test_project_customer_requests(self):
        path = '/admin/Project/my-project/customer_requests'
        from penelope.core.forms.project import Backlog
        with patch.object(Backlog, 'fetch_done') as fetch_done:
            fetch_done.return_value = {}
            self.por_anonymous(path, 403)
            self.por_security_matrix(path, [(('authenticated',),      403),
                                            (('owner',),              403),
                                            (('customer',),           200),
                                            (('external_developer',), 200),
                                            (('internal_developer',), 200),
                                            (('secretary',),          200),
                                            (('project_manager',),    200),
                                            (('administrator',),      200),
                                        ])

    def test_project_add_customer_requests(self):
        path = '/admin/Project/my-project/add_customer_request'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customer_request_view(self):
        path = '/admin/CustomerRequest/my-project_1'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('external_developer',), 403),
                                        (('customer',),           200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customer_request_view_estimations(self):
        path = '/admin/CustomerRequest/my-project_1/estimations'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_customer_request_workflow(self):
        path = '/admin/CustomerRequest/my-project_1/goto_state?state=estimated'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    302),
                                        (('administrator',),      302),
                                       ])

    def test_application_edit(self):
        app = Application(name=u'testing trac')
        prj = self.session.query(Project).get('my-project')
        prj.add_application(app)
        self.session.commit()
        path = '/admin/Application/1/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def add_initial_roles(self):
        for role in (u'internal_developer', u'external_developer', u'customer',
                     u'secretary', u'project_manager'):
            self.session.add(Role(name=role))
        self.session.commit()

    def test_application_with_acl_view(self):
        self.add_initial_roles()
        app = Application(name=u'testing trac')
        prj = self.session.query(Project).get('my-project')
        prj.add_application(app)
        self.session.commit()
        path = '/admin/Application/1'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_trac_with_acl_view(self):
        self.add_initial_roles()
        with patch('penelope.trac.events.add_trac_to_project'):
            app = Application(name=u'testing trac')
            app.application_type = u'trac'
            prj = self.session.query(Project).get('my-project')
            prj.add_application(app)
            self.session.commit()
        path = '/admin/Application/1'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_list(self):
        path = '/admin/TimeEntry'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_add(self):
        path = '/admin/TimeEntry/new'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 200),
                                        (('internal_developer',), 200),
                                        (('secretary',),          200),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_view(self):
        tp = TimeEntry()
        tp.project_id = 'my-project'
        self.session.add(tp)
        self.session.commit()
        path = '/admin/TimeEntry/1'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              200),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 200),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_edit(self):
        tp = TimeEntry(id=1)
        tp.project_id = 'my-project'
        self.session.add(tp)
        self.session.commit()
        path = '/admin/TimeEntry/1/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_edit_in_new(self):
        tp = TimeEntry(id=1)
        tp.workflow_state = u'new'
        tp.project_id = 'my-project'
        self.session.add(tp)
        self.session.commit()
        path = '/admin/TimeEntry/1/edit'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              200),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          403),
                                        (('project_manager',),    200),
                                        (('administrator',),      200),
                                       ])

    def test_tp_workflow(self):
        tp = TimeEntry(id=1)
        tp.project_id = 'my-project'
        self.session.add(tp)
        self.session.commit()
        path = '/admin/TimeEntry/1/goto_state?state=billable'
        self.por_anonymous(path, 403)
        self.por_security_matrix(path, [(('authenticated',),      403),
                                        (('owner',),              403),
                                        (('customer',),           403),
                                        (('external_developer',), 403),
                                        (('internal_developer',), 403),
                                        (('secretary',),          302),
                                        (('project_manager',),    302),
                                        (('administrator',),      302),
                                       ])

#    def test_tp_delete(self):
#        tp = TimeEntry()
#        tp.project_id = 'my-project'
#        self.session.add(tp)
#        self.session.commit()
#        path = '/admin/TimeEntry/1/delete'
#        self.por_anonymous(path, 403, POST=True)
#        self.por_security_matrix(path, [(('authenticated',),      403),
#                                        (('owner',),              302),
#                                        (('customer',),           403),
#                                        (('external_developer',), 403),
#                                        (('internal_developer',), 403),
#                                        (('secretary',),          403),
#                                        (('project_manager',),    302),
#                                        (('administrator',),      302),
#                                       ], POST=True)


SecurityMatrixTest.setUpClass()
