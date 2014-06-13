# -*- coding: utf-8 -*-

from copy import deepcopy

from pyramid import httpexceptions as exc

from js.jqgrid import jqgrid, jqgrid_i18n_en
from fa.bootstrap import actions

from penelope.core.forms import ModelView
from penelope.core.forms import workflow
from penelope.core.fanstatic_resources import migrate_cr
from penelope.core.forms.fast_ticketing import FastTicketing
from penelope.core.lib.helpers import ticket_url, unicodelower
from penelope.core.models import dashboard, tp, DBSession


def configurate(config):
    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='view',
                                  name='',
                                  attr='show',
                                  renderer='fa.bootstrap:templates/admin/show.pt',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='delete',
                                  name='delete',
                                  attr='delete',
                                  renderer='fa.bootstrap:templates/admin/edit.pt',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  renderer='fa.bootstrap:templates/admin/listing.pt',
                                  context='pyramid_formalchemy.resources.ModelListing',
                                  attr='listing',
                                  request_method='GET',
                                  permission='view',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestListingView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='workflow',
                                  name='goto_state',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=workflow.goto_state)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='estimations',
                                  name='estimations.json',
                                  renderer='json',
                                  attr='get_estimations',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='estimations',
                                  name='estimations.html',
                                  attr='get_estimations_html',
                                  renderer='penelope.core.forms:templates/estimations_simple.pt',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='estimations',
                                  name='estimations.json',
                                  renderer='json',
                                  attr='put_estimations',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='estimations',
                                  name='estimations',
                                  attr='estimations',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  renderer='penelope.core.forms:templates/estimations.pt',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='view',
                                  name='tickets',
                                  attr='tickets',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  renderer='penelope.core.forms:templates/customer_request_tickets.pt',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='edit',
                                  name='migrate',
                                  attr='migrate',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  renderer='penelope.core.forms:templates/customer_request_migrate.pt',
                                  view=CustomerRequestModelView)

    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='edit',
                                  name='migrate',
                                  attr='do_migrate',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=CustomerRequestModelView)

    #custom view for adding tickets to a customerrequest
    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='new',
                                  name='fastticketing',
                                  attr='render',
                                  renderer='penelope.core.forms:templates/fast_ticketing.pt',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=FastTicketing)
    #custom view for adding tickets to a customerrequest
    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='new',
                                  name='fastticketing',
                                  attr='render',
                                  renderer='penelope.core.forms:templates/fast_ticketing.pt',
                                  model='penelope.core.models.dashboard.CustomerRequest',
                                  view=FastTicketing)


customer_request_tabs = actions.TabsActions(actions.TabAction("show",
                                                              content="View",
                                                              permission='view',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),
                                            actions.TabAction("tickets",
                                                              content="Tickets",
                                                              permission='view',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'tickets')")),
                                            actions.TabAction("estimations",
                                                              content="Estimations",
                                                              permission='estimations',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'estimations')")),
                                            actions.TabAction("migrate",
                                                              content="Migrate",
                                                              permission='edit',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'migrate')")),
                                            )

customer_request_tabs_without_estimations = actions.TabsActions(actions.TabAction("show",
                                                              content="View",
                                                              permission='view',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),
                                            actions.TabAction("tickets",
                                                              content="Tickets",
                                                              permission='view',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'tickets')")),
                                            actions.TabAction("migrate",
                                                              content="Migrate",
                                                              permission='edit',
                                                              attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'migrate')")),
                                            )

add_ticket = actions.UIButton(id='add_ticket',
                              content='Add ticket',
                              permission='view',
                              _class='btn btn-success',
                              attrs=dict(href="request.model_instance.add_ticket_url(request)"))

add_fast_ticketing = actions.UIButton(id='add_fast_ticketing',
                              content='Fast add tickets',
                              permission='new',
                              _class='btn btn-success',
                              attrs=dict(href="request.fa_url('CustomerRequest', request.model_id, 'fastticketing')"))


class CustomerRequestListingView(ModelView):
    defaults_actions = deepcopy(actions.defaults_actions)
    defaults_actions.update(listing_buttons = actions.Actions())


class CustomerRequestModelView(ModelView):
    actions_categories = ('buttons', 'tabs')
    defaults_actions = deepcopy(actions.defaults_actions)

    def __init__(self, *args, **kwargs):
        super(CustomerRequestModelView, self).__init__(*args, **kwargs)
        self.defaults_actions.update(show_buttons=actions.Actions(actions.edit))
        if self.context.get_instance().filler:
            cr_actions = deepcopy(customer_request_tabs_without_estimations)
        else:
            cr_actions = deepcopy(customer_request_tabs)
        wf = workflow.change_workflow(self.context)
        if wf:
            wf_actions = cr_actions + [wf]
        self.defaults_actions.update(show_tabs = wf_actions)
        self.defaults_actions.update(estimations_tabs = cr_actions)
        self.defaults_actions['show_buttons'].append(add_ticket)
        self.defaults_actions['show_buttons'].append(add_fast_ticketing)

    def delete(self):
        cr = self.context.get_instance()
        if len(cr.get_tickets(self.request)):
            request = self.request
            request.add_message(u'Customer request has tickets. Please remove them first.', type='danger')
            raise exc.HTTPFound(location=request.fa_url('CustomerRequest', cr.id))
        else:
            return self.force_delete()

    @actions.action('estimations')
    def estimations(self):
        """Use http://trirand.com/blog grid widget """
        jqgrid_i18n_en.need()
        jqgrid.need()
        return self.render()

    def get_estimations_html(self):
        items = self.request.model_instance.estimations
        estimations =[ [item.person_type,item.days] for item in items]
        return self.render(estimations=estimations)

    @actions.action('show')
    def tickets(self):
        """Use iframe to render tickets """
        tracs = list(self.request.model_instance.project.tracs)
        if not tracs:
            return None
        trac_url = tracs[0].application_uri(self.request)
        customer_request_id = self.request.model_instance.id
        report_url = '%s/query?customerrequest=%s&iframe=true' % (trac_url, customer_request_id)
        return self.render(report_url=report_url)

    @actions.action('show')
    def migrate(self):
        """Massive time entry migration form"""
        migrate_cr.need()
        context = self.context.get_instance()
        project = context.project
        opts = {}
        opts['crs'] = sorted([cr for cr in project.customer_requests if cr.id != context.id], key=unicodelower)
        opts['current_customer_request'] = context
        opts['back_url'] = '%s/admin/CustomerRequest/%s' % (self.request.application_url, context.id)
        opts['tes'] = context.time_entries
        opts['ticket_url'] = ticket_url
        dates = [t.date for t in context.time_entries]
        dates.sort()
        opts['dates'] = set(dates)
        tickets = [int(t.ticket) for t in context.time_entries]
        tickets.sort()
        opts['tickets'] = set(tickets)
        return self.render(**opts)

    def do_migrate(self):
        from penelope.core.models.tickets import ticket_store

        context = self.context.get_instance()
        cr_id = context.id
        pr_id = context.project_id
        te_ids = self.request.POST.getall('te')
        new_cr = self.request.POST.get('new_cr')
        author = self.request.authenticated_user.email
        tes = DBSession().query(tp.TimeEntry).filter(tp.TimeEntry.id.in_(te_ids))
        if self.request.POST.get('submit') == u'move_time_entries_and_tickets':
            update_tickets = True
        else:
            update_tickets = False

        n_te = 0
        n_ticket = 0

        tickets = set()
        for te in tes:
            te.customer_request_id = new_cr
            tickets.add(te.ticket)
            n_te += 1

        if update_tickets:
            for ticket in tickets:
                t = ticket_store.get_raw_ticket(pr_id, ticket)
                t['customerrequest'] = new_cr
                t.save_changes(comment=u'Massive move operation from Penelope.', author=author)
                n_ticket += 1
            self.request.add_message('%d ticket updated.' % n_ticket)

        self.request.add_message('%d time entries moved.' % n_te)
        raise exc.HTTPFound(location=self.request.fa_url('CustomerRequest', cr_id, 'migrate'))

    def put_estimations(self):
        self.request.model_class = dashboard.Estimation
        self.request.model_name = 'Estimation'
        customer_request_id = self.request.model_instance.id
        response = {'success': True}

        self.data = self.request.POST
        obj_id = self.data.pop('id')
        if obj_id == u'_empty':
            obj_id = ''
        else:
            self.request.model_instance = self.session.query(dashboard.Estimation).get(obj_id)

        action = self.data.pop('oper')

        def process(session=None):
            self.data = dict([('Estimation-%s-%s' % (obj_id, k),v) for k,v in self.data.items()])
            self.data['Estimation-%s-customer_request_id' % obj_id] = customer_request_id
            if session:
                self.fs = self.fs.bind(data=self.data, session=self.session, request=self.request)
            else:
                self.fs = self.fs.bind(data=self.data, request=self.request)
            if self.validate(self.fs):
                self.fs.sync()
                return {'success': True}
            else:
                return {'success': False, 'message': 'Validation error'}

        def add():
            self.fs = self.get_fieldset()
            return process(session=self.session)

        def edit():
            self.fs = self.get_fieldset(id=obj_id)
            msg = process()
            self.sync(self.fs, obj_id)
            return msg

        def delete():
            record = self.request.model_instance
            if record:
                self.session.delete(record)

        if action == 'add': response = add()
        elif action == 'edit': response = edit()
        elif action == 'del': delete()

        self.session.flush()

        return response

    def get_estimations(self):
        """
        Return json for the grid:

          {"records":"13",
           "rows":[
             {"id":"1","cell":["1","2007-10-01","Client 1","100.00","20.00","120.00","note 1"]}],
          }
        """
        items = self.request.model_instance.estimations
        total_days = sum([a.days for a in items])
        len_items = len(items)

        resp = {'records': len_items,
                'userdata':{"days":total_days,
                            "person_type":"Totals:"},
                'rows':[]}

        for item in items:
            resp['rows'].append({'id': str(item.id), 'cell':[item.person_type,
                                                             item.days]})
        return resp

