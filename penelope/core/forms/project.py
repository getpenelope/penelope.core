# -*- coding: utf-8 -*-

from copy import deepcopy
import json

from pyramid.httpexceptions import HTTPFound
from pyramid import httpexceptions as exc
from pyramid_skins import SkinObject

from fa.bootstrap import actions

from penelope.core.backlog import Backlog
from penelope.core.models import dashboard
from penelope.core.models import DBSession
from penelope.core.forms import ModelView


def configurate(config):
    #custom view for project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='',
        attr='documentation',
        renderer='fa.bootstrap:templates/admin/show.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        renderer='penelope.core.forms:templates/project_listing.pt',
        attr='datatable',
        context='pyramid_formalchemy.resources.ModelListing',
        request_method='GET',
        permission='listing',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for adding an application to the project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='new',
        name='add_group',
        attr='add_group',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='new',
        name='add_group',
        attr='add_group',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for adding an application to the project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='new',
        name='add_application',
        attr='add_application',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='new',
        name='add_application',
        attr='add_application',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for configuration section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='edit',
        name='configuration',
        attr='configuration',
        renderer='penelope.core.forms:templates/configuration.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for documentation section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='metadata',
        name='metadata',
        attr='show',
        renderer='penelope.core.forms:templates/project.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for customer_requests section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='customer_requests',
        attr='customer_requests',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for contracts section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='contracts',
        attr='contracts',
        renderer='penelope.core.forms:templates/contracts.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)


    #custom view for tickets section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='tickets',
        attr='tickets',
        renderer='penelope.core.forms:templates/tickets.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for time_entries section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='time_entries',
        name='time_entries',
        attr='time_entries',
        renderer='penelope.core.forms:templates/time_entries.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for documentation section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='applications',
        attr='applications',
        renderer='penelope.core.forms:templates/configurate_apps.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for adding a customer request to the project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='new',
        name='add_customer_request',
        attr='add_customer_request',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='new',
        name='add_customer_request',
        attr='add_customer_request',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    #custom view for adding a contract to the project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='new',
        name='add_contract',
        attr='add_contract',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='new',
        name='add_contract',
        attr='add_contract',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)


    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='toggle_favorite',
        attr='toggle_favorite',
        model='penelope.core.models.dashboard.Project',
        view=ProjectModelView)


class ProjectModelView(ModelView):
    actions_categories = ('buttons', 'tabs', 'subtabs')
    defaults_actions = deepcopy(actions.defaults_actions)

    def __init__(self, *args, **kwargs):
        super(ProjectModelView, self).__init__(*args, **kwargs)
        self.defaults_actions.update(show_buttons=actions.Actions(actions.edit))
        self.defaults_actions.update(listing_buttons=actions.Actions())
        self.defaults_actions.update(documentation_buttons=actions.Actions())

    def delete(self):
        project = self.context.get_instance()
        request = self.request
        STOP = False
        if len(project.groups):
            request.add_message(u'Project has existing groups. Please remove them first.', type='danger')
            STOP = True
        if len(project.applications):
            request.add_message(u'Project has existing applications. Please remove them first.', type='danger')
            STOP = True
        if len(project.customer_requests):
            request.add_message(u'Project has existing customer_requests. Please remove them first.', type='danger')
            STOP = True
        if len(project.time_entries):
            request.add_message(u'Project has existing time entries. Please remove them first.', type='danger')
            STOP = True

        if STOP:
            raise exc.HTTPFound(location=request.fa_url('Project', project.id))
        else:
            request.fa_parent_url = lambda : request.fa_url(request.model_name)
            return self.force_delete()

    def add_group(self, *args, **kwargs):
        self.request.model_class = dashboard.Group
        self.request.model_name = dashboard.Group.__name__
        self.request.form_action = ['Project', self.request.model_id, 'add_group']
        return self.new()

    def add_application(self, *args, **kwargs):
        self.request.model_class = dashboard.Application
        self.request.model_name = dashboard.Application.__name__
        self.request.form_action = ['Project', self.request.model_id, 'add_application']
        return self.new()

    def add_customer_request(self, *args, **kwargs):
        self.request.model_class = dashboard.CustomerRequest
        self.request.model_name = dashboard.CustomerRequest.__name__
        self.request.form_action = ['Project', self.request.model_id, 'add_customer_request']
        return self.new()

    def add_contract(self, *args, **kwargs):
        self.request.model_class = dashboard.Contract
        self.request.model_name = dashboard.Contract.__name__
        self.request.form_action = ['Project', self.request.model_id, 'add_contract']
        return self.new()

    def all_customer_requests(self):
        session = DBSession()
        return self.request.filter_viewables(
                        session.query(dashboard.CustomerRequest)\
                               .filter(dashboard.CustomerRequest.project ==\
                                       self.context.get_instance()))

    @actions.action()
    def time_entries(self, *args, **kwargs):
        context = self.context.get_instance()
        page = self.get_page(collection=context.time_entries)
        pager = page.pager(**self.pager_args)
        return self.render(pager=pager, items=page)

    @actions.action()
    def tickets(self, *args, **kwargs):
        return self.render(customer_requests=self.all_customer_requests())

    @actions.action()
    def contracts(self, *args, **kwargs):
        context = self.context.get_instance()
        page = self.get_page(collection=context.contracts)
        pager = page.pager(**self.pager_args)
        return self.render(pager=pager, items=page)

    @actions.action()
    def customer_requests(self, *args, **kwargs):
        project = self.context.get_instance()
        params = Backlog(self.request).backlog(projects=[project])
        params['request'] = self.request
        params['context'] = self.request.context
        params['all_contracts'] = project.contracts_by_state()
        params['multiple_bgb'] = False
        # override backlog permissions.
        # if the user is not a developer/pm/admin, deny the view of placement and done time entries
        roles = self.request.authenticated_user.roles_in_context(project)

        if not roles.intersection(set(['administrator', 'project_manager', 'internal_developer','secretary'])):
            params['can_view_placement'] = False

        return SkinObject('tekken')(**params)


    @actions.action('documentation')
    def documentation(self, *args, **kwargs):
        raise HTTPFound('%s/applications' % self.request.current_route_url())

    @actions.action('configuration')
    def configuration(self, *args, **kwargs):
        context = self.context.get_instance()
        return self.render(groups=context.groups)

    @actions.action('applications')
    def applications(self, *args, **kwargs):
        context = self.context.get_instance()
        return self.render(applications=context.applications)

    def toggle_favorite(self, *args, **kwargs):
        user = self.request.authenticated_user
        context = self.context.get_instance()
        if user not in context.favorite_users:
            context.favorite_users.append(user)
            self.request.add_message(u'Project %s has been marked as favorite.' % context.name, 'success')
        else:
            context.favorite_users.remove(user)
            self.request.add_message(u'Project %s has been unmarked as favorite.' % context.name, 'success')
        raise HTTPFound(self.request.fa_url('Project', context.id))


    @actions.action('listing')
    def datatable(self, **kwargs):
        result = super(ProjectModelView, self).datatable(**kwargs)

        fs = result['fs']
        fs.configure(pk=True, readonly=True)
        viewed_projects = set(fs.rows.items)

        columns = ['name', 'customer', 'manager', 'customer_requests', 'groups', 'activated', 'id']
        self.pick_columns(fs, columns)

        user = self.request.authenticated_user
        favorite_projects = set(p.id for p in set(user.favorite_projects).intersection(viewed_projects))

        return dict(result,
                    columns=columns,
                    js_favorite_projects=json.dumps(list(favorite_projects)))
