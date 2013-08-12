# -*- coding: utf-8 -*-

from copy import deepcopy
from fa.bootstrap import actions
from penelope.core.forms import ModelView
from penelope.core.forms import workflow


def configurate(config):
    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='view',
                                  name='',
                                  attr='show',
                                  renderer='fa.bootstrap:templates/admin/show.pt',
                                  model='penelope.core.models.dashboard.Contract',
                                  view=ContractModelView)
    config.formalchemy_model_view('admin',
                                  request_method='GET',
                                  permission='workflow',
                                  name='goto_state',
                                  model='penelope.core.models.dashboard.Contract',
                                  view=workflow.goto_state)


contract_tabs = actions.TabsActions(actions.TabAction("show",
                                                      content="View",
                                                      permission='view',
                                                      attrs=dict(href="request.fa_url(request.model_name, request.model_id, '')")),)


class ContractModelView(ModelView):
    actions_categories = ('buttons', 'tabs')
    defaults_actions = deepcopy(actions.defaults_actions)

    def __init__(self, *args, **kwargs):
        super(ContractModelView, self).__init__(*args, **kwargs)
        self.defaults_actions.update(show_buttons=actions.Actions(actions.edit))
        cr_actions = deepcopy(contract_tabs)
        wf = workflow.change_workflow(self.context)
        if wf:
            cr_actions.append(wf)
        self.defaults_actions.update(show_tabs = cr_actions)
