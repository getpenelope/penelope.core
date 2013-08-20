# -*- coding: utf-8 -*-

import datetime
import unittest2

from penelope.core.smartadd import SmartAddParser


class TestSmartAddParser(unittest2.TestCase):

    def setUp(self):
        pass

    def test_plain(self):
        """
        A simple text with no tags
        """
        par = SmartAddParser(u'foo bar baz')
        self.assertEquals(par.unparsed, u'foo bar baz')
        self.assertIsNone(par.project_id)


    def test_strip(self):
        """
        Description has no leading or trailing spaces
        """
        par = SmartAddParser(u'  foo bar baz ')
        self.assertEquals(par.unparsed, u'foo bar baz')
        self.assertIsNone(par.project_id)

    #
    # PROJECT
    #
    # XXX what if the @ is used more than once? error or parse the longest found
    #     now it only gives an error if no tag matches

    def test_project(self):
        """
        A project tag that matches an existing project
        """
        projects = {'foo': '37', 'bar': '2', 'baz': '3'}
        par = SmartAddParser(u'this is some @foo stuff', projects=projects)
        self.assertEquals(par.unparsed, u'this is some stuff')
        self.assertEquals(par.project_id, '37')


    def test_project_ignorecase(self):
        """
        A project name is found if the case is different
        """
        projects = {'FOO': '37', 'bar': '2', 'baz': '3'}
        par = SmartAddParser(u'this is some @Foo stuff ^1', projects=projects)
        self.assertEqual([u'Ticket is missing'], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'this is some stuff',
            'project_id': '37',
            }, par.parsed_time_entry)


    def test_project_notfound(self):
        """
        A project control character is used but the project is not found
        """
        par = SmartAddParser(u'this is some @foo stuff #1 ^:30',
                             projects={'bar': '2', 'baz': '3'},
                             available_tickets=[1])
        self.assertEqual([u'Project not found'],
                          par.validation_errors())


    def test_project_first(self):
        """
        Only matches the first tag
        """
        projects = {'foo': '37', 'barbaz': '2'}
        par = SmartAddParser(u'this is some @foo @barbaz stuff ^1',
                             projects=projects)
        self.assertEqual([u'Ticket is missing'], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'this is some @barbaz stuff',
            'project_id': '37',
            }, par.parsed_time_entry)


    def test_project_longest(self):
        """
        Matches the longest project name, if there are several matches
        """
        projects = {'foo': '37', 'foobar': '2', 'foobaz': '3', 'fooblabla': '5'}
        par = SmartAddParser(u'this is some @fooblabla stuff ^1',
                             projects=projects)
        self.assertEqual([u'Ticket is missing'], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'this is some stuff',
            'project_id': '5',
            }, par.parsed_time_entry)


    def test_project_waitingfortickets(self):
        projects = {'foo': '37', 'foobar': '2', 'foobaz': '3', 'fooblabla': '5'}
        par = SmartAddParser(u'omg omg @fooblabla hey ^1 #', projects=projects)
        self.assertEqual([u'Ticket is missing'], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'omg omg hey #',
            'project_id': '5',
            }, par.parsed_time_entry)


    #
    # TICKET
    #

    def test_ticket(self):
        """
        A ticket tag that matches an existing ticket
        """
        tickets = [1, 2, 3, 4, 45]
        par = SmartAddParser(u'fixed #45 for ever ^1', available_tickets=tickets)
        self.assertEqual([u'Project is missing'], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'fixed for ever',
            'tickets': ['45'],
            }, par.parsed_time_entry)

    def test_ticket_notfound(self):
        """
        Missing tickets raise an error even when multiple tickets are selected.
        """
        par = SmartAddParser(u'@proj #3 #47 works for me ^1:00',
                             projects={'proj': 'proj'},
                             available_tickets=[1, 2, 3, 4, 45])
        self.assertEqual([u'Ticket #47 not found or customer request already invoiced'],
                          par.validation_errors())
        par = SmartAddParser(u'@proj #47 #3 #2 #66 works for me ^1:00',
                             projects={'proj': 'proj'},
                             available_tickets=[1, 2, 3, 4, 45])
        self.assertEqual([u'Tickets #47, #66 not found or customer request already invoiced'],
                          par.validation_errors())


    def test_ticket_callable(self):
        """
        A ticket list may be provided by a callable. The project_id is then passed to the callable.
        """
        def ticket_provider(project_code):
            if project_code == 'one':
                return [1]
            if project_code == 'two':
                return [2]
        par = SmartAddParser(u'@one #1 ^0:20 blabla',
                             projects={'one': 'one'},
                             available_tickets=ticket_provider)
        self.assertEqual([], par.validation_errors())

        par = SmartAddParser(u'@two #2 ^0:20 blabla',
                             projects={'two': 'two'},
                             available_tickets=ticket_provider)
        self.assertEqual([], par.validation_errors())

        par = SmartAddParser(u'@one #2 ^0:20 blabla',
                             projects={'one': 'one'},
                             available_tickets=ticket_provider)
        self.assertEqual([u'Ticket #2 not found or customer request already invoiced'],
                          par.validation_errors())

        par = SmartAddParser(u'@two #1 ^0:20 blabla',
                             projects={'two': 'two'},
                             available_tickets=ticket_provider)
        self.assertEqual([u'Ticket #1 not found or customer request already invoiced'],
                          par.validation_errors())


    def test_project_name(self):
        """
        The parser matches the project name, not the id.
        """
        par = SmartAddParser(u'@proj_name #47 works for me ^1:00',
                             projects={'proj_name': 'pr_id'},
                             available_tickets=[1, 2, 3, 4, 47])
        self.assertEqual([], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'works for me',
            'tickets': ['47'],
            }, par.parsed_time_entry)


    def test_project_name_uppercase(self):
        """
        The match is case insensitive.
        """
        par = SmartAddParser(u'@Proj_Name #47 works for me ^1:00',
                             projects={'Proj_Name': 'pr_id'},
                             available_tickets=[1, 2, 3, 4, 47])
        self.assertEqual([], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'works for me',
            'tickets': ['47'],
            }, par.parsed_time_entry)


    def test_project_name_space(self):
        """
        The project name can contain spaces.
        """
        par = SmartAddParser(u'@proj name #47 works for me ^1:00',
                             projects={'proj name': 'pr_id'},
                             available_tickets=[1, 2, 3, 4, 47])
        self.assertEqual([], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'works for me',
            'tickets': ['47'],
            }, par.parsed_time_entry)



    def test_project_with_space(self):
        """
        A project name may contain spaces (regression #85)
        """
        par = SmartAddParser(u'@my project #47 works for me ^1:00',
                             projects={'my project': 'proj'},
                             available_tickets=[1, 2, 3, 4, 47])
        self.assertEqual([], par.validation_errors())
        self.assertDictContainsSubset({
            'description': u'works for me',
            'tickets': ['47'],
            }, par.parsed_time_entry)


    def test_multi_tickets(self):
        """
        More than one ticket can be specified. Duration will be equally split.
        """
        tickets = [1, 2, 3, 4, 6, 10, 45, 66, 100, 666]
        projects = {'my project': 7}
        par = SmartAddParser(u'@my project fixed #6 #66 #45 lorem ipsum ^1:30',
                             projects=projects,
                             available_tickets=tickets)
        self.assertEquals(par.unparsed, u'fixed lorem ipsum')
        self.assertDictContainsSubset({
            'project_id': 7,
            'description': u'fixed lorem ipsum',
            'tickets': ['6', '66', '45'],
            'hours': datetime.timedelta(0, 5400),
            }, par.parsed_time_entry)



    def test_repeated_multi_tickets(self):
        """
        Tickets that are repeated only count for one.
        """
        tickets = [1, 2, 3, 4, 6, 10, 45, 66, 100, 666]
        projects = {'my project': 7}
        par = SmartAddParser(u'@my project fixed #6 #66 #45 #66 #45 lorem ipsum ^1:30',
                             projects=projects,
                             available_tickets=tickets)
        self.assertEquals(par.unparsed, u'fixed lorem ipsum')
        self.assertDictContainsSubset({
            'project_id': 7,
            'description': u'fixed lorem ipsum',
            'tickets': ['6', '66', '45'],
            'hours': datetime.timedelta(0, 5400),
            }, par.parsed_time_entry)




    #
    # HOURS
    #
    # XXX what if the ^ is used more than once? error?

    def test_hours(self):
        """
        Looks for a time like ^HH:MM
        """
        par = SmartAddParser(u'Took half an hour ^0:30.')
        self.assertDictContainsSubset({
            'description': u'Took half an hour .',
            'hours': datetime.timedelta(minutes=30),
            }, par.parsed_time_entry)


    def test_hours_integer(self):
        """
        ^3 is short for ^03:00
        """
        par = SmartAddParser(u'Took two ^2 hours')
        self.assertDictContainsSubset({
            'description': u'Took two hours',
            'hours': datetime.timedelta(hours=2),
            }, par.parsed_time_entry)


    def test_hours_onlyminutes(self):
        """
        ^:20 is short for ^00:20
        """
        par = SmartAddParser(u'Took thirty ^:30 minutes')
        self.assertDictContainsSubset({
            'description': u'Took thirty minutes',
            'hours': datetime.timedelta(minutes=30),
            }, par.parsed_time_entry)


    def test_hours_error(self):
        """
        A time control character is used but the time could not be parsed
        """
        par = SmartAddParser(u'@foo #3 this is^wrong',
                             projects={'foo':'foo'},
                             available_tickets=[3])
        self.assertEqual([u'Could not parse time'],
                          par.validation_errors())


    #
    # DATE
    #

    def test_dates(self):
        """
        A project tag that matches an existing project
        """
        projects = {'foo': '37', 'bar': '2', 'baz': '3'}
        par = SmartAddParser(u'!today this is some @foo stuff', projects=projects)
        self.assertEquals(par.unparsed, u'this is some stuff')
        self.assertEquals(par.date, datetime.date.today())

        par = SmartAddParser(u'this is !yesterday some @foo stuff', projects=projects)
        self.assertEquals(par.unparsed, u'this is some stuff')
        self.assertEquals(par.date, datetime.date.today() - datetime.timedelta(days=1))

        par = SmartAddParser(u'this is !foobar some @foo stuff #3 ^2:30',
                             projects=projects,
                             available_tickets=[3])

        self.assertEquals(par.unparsed, u'this is !foobar some stuff')
        self.assertEqual([u'Cannot parse date'],
                          par.validation_errors())

    #
    # Required tags
    #

    def test_complete(self):
        """
        Checks that all the required tags are present, and description is there
        """
        par = SmartAddParser(u'')
        self.assertEqual([u'Project is missing', u'Time is missing', u'Ticket is missing', u'Description is empty'],
                          par.validation_errors())

        par = SmartAddParser(u'bla bla bla')
        self.assertEqual([u'Project is missing', u'Time is missing', u'Ticket is missing'],
                          par.validation_errors())

        par = SmartAddParser(u'bla bla bla @ppp', projects={'ppp': 1})
        self.assertEqual([u'Time is missing', u'Ticket is missing'],
                          par.validation_errors())

        par = SmartAddParser(u'bla bla bla @ppp #2', projects={'ppp': 1}, available_tickets=[2])
        self.assertEqual([u'Time is missing'],
                          par.validation_errors())




if __name__ == '__main__':
    unittest2.main()

