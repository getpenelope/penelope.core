# -*- coding: utf-8 -*-

from copy import deepcopy
from fa.bootstrap import actions
from pyramid import httpexceptions as exc
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
    config.formalchemy_model_view('admin',
                                  request_method='POST',
                                  permission='delete',
                                  name='delete',
                                  attr='delete',
                                  renderer='fa.bootstrap:templates/admin/edit.pt',
                                  model='penelope.core.models.dashboard.Contract',
                                  view=ContractModelView)



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

    def delete(self):
        cr = self.context.get_instance()
        if cr.customer_requests:
            request = self.request
            request.add_message(u'Contract has customer requests. Please remove them first.', type='danger')
            raise exc.HTTPFound(location=request.fa_url('Contract', cr.id))
        else:
            return self.force_delete()

