import jsonrpc.proxy
import unittest2
import transaction
import datetime

from penelope.core.models.dashboard import User, Customer, CustomerRequest, Application, Project
from penelope.core.models import DBSession


class TestJSONRPCProxy(unittest2.TestCase):

    def setUp(self):
        self.proxy = jsonrpc.proxy.JSONRPCProxy('', path='/apis/json/dashboard')

    def test_get_user_by_attribute(self):
        session = DBSession()
        user = User(email=u'user@dummy.it')
        session.add(user)
        transaction.commit()
        #Get the user by email
        resp = self.proxy.get_user_by_email('user@dummy.it')
        self.assertEqual(resp['email'], u'user@dummy.it')

    def test_get_user_by_openid(self):
        session = DBSession()
        user = User(email=u'other_user@dummy.it')
        user.add_openid(u'other_user@dummy.it')
        session.add(user)
        transaction.commit()

        resp = self.proxy.get_user_by_openid('other_user@dummy.it')
        self.assertTrue(u'other_user@dummy.it' in resp['openids'])

    def test_get_customer_by_name(self):
        customer_name = u'A rich customer'
        session = DBSession()
        customer = Customer(name=customer_name)
        session.add(customer)
        transaction.commit()

        resp = self.proxy.get_customer_by_name(customer_name)
        self.assertEqual(resp['name'], customer_name)

    def test_get_project_by_name(self):
        project_name = u'A nice project'
        customer_name = u'A good customer'
        session = DBSession()
        project = Project(name=project_name)
        customer = Customer(name=customer_name)
        customer.add_project(project)
        session.add(customer)
        transaction.commit()

        resp = self.proxy.get_project_by_name(project_name)
        self.assertEqual(resp['name'], project_name)

    def test_project_attributes(self):
        project_name = u'Another nice project'
        customer_name = u'A very good customer'
        session = DBSession()
        project = Project(name=project_name)
        customer = Customer(name=customer_name)
        customer.add_project(project)
        applications1 = Application(name=u'Trac')
        applications2 = Application(name=u'Svn')
        customerR1 = CustomerRequest(name=u'A bad request')
        customerR2 = CustomerRequest(name=u'A good request')
        project.add_application(applications1)
        project.add_application(applications2)
        project.add_customer_request(customerR1)
        project.add_customer_request(customerR2)
        session.add(customer)
        transaction.commit()

        resp = self.proxy.get_project_by_name(project_name)
        self.assertTrue(u'Trac' in resp['applications'])
        self.assertTrue(u'another-nice-project_1' in [item for sublist in resp['customer_requests'] for item in sublist])
        self.assertTrue(u'another-nice-project_2' in [item for sublist in resp['customer_requests'] for item in sublist])
        self.assertTrue(2, len(resp['customer_requests']))
        self.assertTrue(2, len(resp['applications']))

    def test_not_found_user(self):
        resp = self.proxy.get_user_by_email('nonexisting@dummy.it')
        self.assertEqual(resp['message'], u'No user found in db for nonexisting@dummy.it mail address')

        resp = self.proxy.get_user_by_email('nonexisting@dummy.it')
        self.assertEqual(resp['message'], u'No user found in db for nonexisting@dummy.it mail address')

        resp = self.proxy.get_user_by_openid('nonexisting@dummy.it')
        self.assertEqual(resp['message'], u'No user found in db for nonexisting@dummy.it openid')

    def test_not_found_customer(self):
        resp = self.proxy.get_customer_by_name('nonexistingcustomer')
        self.assertEqual(resp['message'], u'No customer found in db for nonexistingcustomer name')

    def test_not_found_project(self):
        resp = self.proxy.get_project_by_name('nonexistingproject')
        self.assertEqual(resp['message'], u'No project found in db for nonexistingproject name')

    def test_time_entry_creation(self):
        """
        This test check time entry parameters
        """
        #customer data
        customer_name = u'RFCCustomer'
        #project data
        project_name = u'A new project'
        project_id = 'a-new-project'
        #entry data
        entry_date = datetime.date(2011, 05, 26)
        entry_hours = '2:30'
        entry_location = u'RedTurtle Technology'
        entry_description = u'Trying to create ticket for API tests'
        entry_ticket = '45'

        #Start to create customer, project and time entry for project
        session = DBSession()
        project = Project(name=project_name, id=project_id)
        customer = Customer(name=customer_name)
        customer.add_project(project)
        session.add(customer)
        transaction.commit()

        #Try to get errors
        resp = self.proxy.create_new_simple_time_entry(1, entry_date,
                                                       entry_hours, entry_description,
                                                       entry_location, project_id)
        self.assertEqual(resp['message'], u"'int' object has no attribute 'decode'")

        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       entry_date,
                                                       u'9000',
                                                       entry_description,
                                                       entry_location,
                                                       project_id)

        self.assertEqual(resp['message'], u'Cannot parse time (must be HH:MM)')

        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       entry_date,
                                                       u'19:40',
                                                       entry_description,
                                                       entry_location,
                                                       project_id)

        self.assertEqual(resp['message'], u'Time value too big (must be <= 16:00)')

        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       entry_date,
                                                       entry_hours,
                                                       entry_description,
                                                       entry_location,
                                                       100)
        self.assertEqual(resp['message'], u'Not able to get the project with id 100')

        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       '2011 01 01',
                                                       entry_hours,
                                                       entry_description,
                                                       entry_location,
                                                       100)
        self.assertEqual(resp['message'],  u"time data '2011 01 01' does not match format '%Y-%m-%d'")

        #Let's try to create a simple time entry
        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       entry_date,
                                                       entry_hours,
                                                       entry_description,
                                                       entry_location,
                                                       project_id)

        self.assertRegexpMatches(resp['message'], u'Correctly added time entry \d+ for %s ticket #%s' %(project_id, entry_ticket))

        resp = self.proxy.create_new_simple_time_entry(entry_ticket,
                                                       entry_date,
                                                       entry_hours,
                                                       '',
                                                       entry_location,
                                                       project_id)
        self.assertEqual(resp['message'], u"Description is required.")

        #Now try to create a more complex time entry
        entry_start = datetime.datetime(2011, 01, 01, 15, 30)
        entry_end = datetime.datetime(2011, 01, 01, 17, 30)
        entry_ticket = '#99'

        resp = self.proxy.create_new_advanced_time_entry(99,
                                                         entry_start,
                                                         entry_end,
                                                         entry_description,
                                                         entry_location,
                                                         10)
        self.assertEqual(resp['message'], u"'int' object has no attribute 'decode'")

        resp = self.proxy.create_new_advanced_time_entry(entry_ticket,
                                                         entry_start,
                                                         entry_end,
                                                         entry_description,
                                                         entry_location,
                                                         100)
        self.assertEqual(resp['message'], u'Not able to get the project with id 100')

        resp = self.proxy.create_new_advanced_time_entry(entry_ticket,
                                                         '2011 08 24',
                                                         entry_end,
                                                         entry_description,
                                                         entry_location,
                                                         10)
        self.assertEqual(resp['message'], u"time data '2011 08 24' does not match format '%Y-%m-%d %H:%M:%S'")

        resp = self.proxy.create_new_advanced_time_entry(entry_ticket,
                                                         entry_start,
                                                         entry_end,
                                                         entry_description,
                                                         entry_location,
                                                         project_id)
        self.assertRegexpMatches(resp['message'], u'Correctly added time entry \d+ for %s ticket #%s' %(project_id, entry_ticket))


if __name__ == '__main__':
    unittest2.main()
