# -*- coding: utf-8 -*-
from fa.bootstrap import actions
from copy import deepcopy

from penelope.core.forms import ModelView, workflow


def configurate(config):
    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='view',
        name='',
        attr='show',
        renderer='fa.bootstrap:templates/admin/show.pt',
        model='penelope.core.models.tp.TimeEntry',
        view=TimeEntryModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='edit',
        name='edit',
        attr='edit',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.tp.TimeEntry',
        view=TimeEntryModelView)

    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.tp.TimeEntry',
        view=TimeEntryModelView)

    config.formalchemy_model_view('admin',
        request_method='GET',
        permission='workflow',
        name='goto_state',
        model='penelope.core.models.tp.TimeEntry',
        view=workflow.goto_state)

    config.formalchemy_model_view('admin',
        view='penelope.core.forms.ModelView',
        context='pyramid_formalchemy.resources.ModelListing',
        model='penelope.core.models.tp.TimeEntry',
        renderer='pyramid_formalchemy:templates/admin/listing.pt',
        attr='listing',
        request_method='GET',
        permission='listing')


timeentry_tabs = actions.TabsActions(actions.TabAction("show",
    content="View",
    permission='view',
    attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")), )


class TimeEntryModelView(ModelView):
    actions_categories = ('buttons', 'tabs')
    defaults_actions = deepcopy(actions.defaults_actions)

    def __init__(self, *args, **kwargs):
        super(TimeEntryModelView, self).__init__(*args, **kwargs)
        self.defaults_actions.update(show_tabs=deepcopy(timeentry_tabs))
        wf = workflow.change_workflow(self.context)
        if wf:
            self.defaults_actions['show_tabs'].append(wf)

    def delete(self):
        """
        For TimeEntry we are always forcing to delete.
        No additional validation
        """
        return self.force_delete()

