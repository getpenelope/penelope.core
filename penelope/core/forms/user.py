# -*- coding: utf-8 -*-
import collections
from zope.interface import implements
from copy import deepcopy
from datetime import datetime, timedelta

from pyramid import httpexceptions as exc
from pyramid_formalchemy import resources
from fa.bootstrap import actions

from penelope.core.fanstatic_resources import user_stats
from penelope.core.forms import ModelView
from penelope.core.forms.renderers import ProjectRelationRenderer
from penelope.core.interfaces import IManageView
from penelope.core.models import dashboard, tp, DBSession
from penelope.core.notifications import notify_user_with_welcoming_mail
from penelope.core.lib.helpers import timedelta_as_work_hours


def configurate(config):
    #custom view for user
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='',
        attr='show',
        renderer='penelope.core.forms:templates/user.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        renderer='penelope.core.forms:templates/user_listing.pt',
        attr='datatable',
        context=ModelListing,
        request_method='GET',
        permission='listing',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    #custom view for tokens section
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='edit',
        name='user_tokens',
        attr='user_tokens',
        renderer='penelope.core.forms:templates/user_tokens.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='costs',
        name='user_costs',
        attr='user_costs',
        renderer='penelope.core.forms:templates/user_costs.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='stats',
        name='user_stats',
        attr='user_stats',
        renderer='penelope.core.forms:templates/user_stats.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='stats',
        name='user_stats.json',
        attr='json_user_stats',
        renderer='json',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='edit',
        name='send_user_invitation',
        attr='send_user_invitation',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    #custom view for adding a customer request to the project
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='costs',
        name='add_cost',
        attr='add_cost',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='costs',
        name='add_cost',
        attr='add_cost',
        renderer='penelope.core.forms:templates/new.pt',
        model='penelope.core.models.dashboard.User',
        view=UserModelView)


send_user_invitation = actions.UIButton(id='send_user_invitation',
    content='Send user invitation',
    permission='edit',
    _class='btn btn-success',
    attrs=dict(href="request.fa_url('User', request.model_id, 'send_user_invitation')"))


user_tabs = actions.Actions(
        actions.TabAction("show",
            content="View",
            permission='view',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),
        actions.TabAction("user_tokens",
            content="User tokens",
            permission='edit',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'user_tokens')")),
        actions.TabAction("costs",
            content="User costs",
            permission='costs',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'user_costs')")),
        actions.TabAction("stats",
            content="User stats",
            permission='stats',
            attrs=dict(href="request.fa_url(request.model_name, request.model_id, 'user_stats')")),
    )

add_costs = actions.Actions(
        actions.UIButton(id='add_cost',
            content='Add user cost',
            permission='costs',
            _class='btn btn-success',
            attrs=dict(href="request.fa_url('User', request.model_id, 'add_cost')")),
        )

class ModelListing(resources.ModelListing):
    implements(IManageView)


class UserModelView(ModelView):
    actions_categories = ('buttons', 'tabs')

    defaults_actions = deepcopy(actions.defaults_actions)
    defaults_actions['show_buttons'].append(send_user_invitation)
    defaults_actions.update(show_tabs=user_tabs)
    defaults_actions.update(user_costs_tabs=user_tabs)
    defaults_actions.update(user_costs_buttons=add_costs)
    defaults_actions.update(user_stats_tabs=user_tabs)

    @actions.action('show')
    def user_tokens(self, *args, **kwargs):
        context = self.context.get_instance()
        return self.render(user=context)

    @actions.action('user_costs')
    def user_costs(self, *args, **kwargs):
        context = self.context.get_instance()
        page = self.get_page(collection=context.costs)
        pager = page.pager(**self.pager_args)
        return self.render(pager=pager, items=page)

    @actions.action('user_costs')
    def add_cost(self, *args, **kwargs):
        self.request.model_class = dashboard.Cost
        self.request.model_name = dashboard.Cost.__name__
        self.request.form_action = ['User', self.request.model_id, 'add_cost']
        if self.request.method == 'POST':
            self.request.POST.update({'next': self.request.fa_url('User', self.request.model_id, 'user_costs')})
        return self.new()

    @actions.action('listing')
    def datatable(self, **kwargs):
        result = super(UserModelView, self).datatable(**kwargs)

        fs = result['fs']
        fs.configure(pk=False, readonly=True)

        columns = ['email', 'fullname', 'roles', 'project_manager', 'active']
        self.pick_columns(fs, columns)

        fs._render_fields['project_manager']._get_renderer = lambda: ProjectRelationRenderer(fs._render_fields['project_manager'])

        return dict(result,
                    columns=columns)

    def delete(self):
        user = self.context.get_instance()
        request = self.request
        if not user.active:
            request.add_message(u'User is already inactive. You cannot remove it.', type='danger')
            raise exc.HTTPFound(location=request.fa_url('User', user.id))
        else:
            user.active = False
            request.add_message(u'User deactivated.', type='success')
            raise exc.HTTPFound(location=request.fa_url('User', user.id))

    def send_user_invitation(self):
        user = self.context.get_instance()
        notify_user_with_welcoming_mail(user.email)
        request = self.request
        request.add_message(u'Invitation email send.', type='success')
        raise exc.HTTPFound(location=request.fa_url('User', user.id))

    @actions.action('user_stats')
    def user_stats(self, *args, **kwargs):
        context = self.context.get_instance()
        user_stats.need()
        return self.render(user=context)

    def json_user_stats(self, *args, **kwargs):

        user = self.context.get_instance()
        now = datetime.now().date()
        now = datetime(2013,4,20)
        week_ago = now - timedelta(weeks=1)

        colors = ["#637b85", "#2c9c69", "#dbba34", "#c62f29", "#F7464A",]
        project_hours = collections.defaultdict(float)
        dayofweek_hours = collections.defaultdict(float)

        tp_last_week = DBSession().query(tp.TimeEntry)\
                                  .filter(tp.TimeEntry.author_id==user.id)\
                                  .filter(tp.TimeEntry.date > week_ago)\
                                  .filter(tp.TimeEntry.date <= now)
        for t in tp_last_week:
            dayofweek_hours[t.date] += timedelta_as_work_hours(t.hours)
            project_hours[t.project.name] += t.hours_as_work_days

        project_hours = project_hours.items()
        project_hours.sort(key=lambda t: t[1], reverse=True)
        project_hours = project_hours[:5]

        last_week_hours = [{'value': p[1], 'color':colors[n]} for n,p in enumerate(project_hours)]
        last_week_hours_legend = [{'label': p[0], 'value': p[1]} for p in project_hours]

        dayofweek_hours = dayofweek_hours.items()
        dayofweek_hours.sort()

        last_week_dow = {
                'labels' : [a[0].strftime('%A') for a in dayofweek_hours],
                'datasets' : [
                    {
                        'fillColor' : "rgba(151,187,205,0.5)",
                        'strokeColor' : "rgba(151,187,205,1)",
                        'pointColor' : "rgba(151,187,205,1)",
                        'pointStrokeColor' : "#fff",
                        'data' : [a[1] for a in dayofweek_hours]
                        },
                    ]
                }

        return {'last_week_hours': last_week_hours,
                'last_week_hours_legend': last_week_hours_legend,
                'last_week_dow': last_week_dow}
