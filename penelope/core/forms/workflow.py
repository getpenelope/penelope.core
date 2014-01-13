# -*- coding: utf-8 -*-
from pyramid.threadlocal import get_current_request
from fa.bootstrap import actions
from webob.exc import HTTPFound
from repoze.workflow import WorkflowError
from repoze.workflow import get_workflow


def goto_state(context, request):
    state = request.params.get('state')
    if not state:
        request.add_message(u'Missing state parameter.', 'error')
        return HTTPFound(location=request.fa_url(request.model_name, request.model_id))
    try:
        workflow = get_workflow(request.model_instance, request.model_name)
        workflow.transition_to_state(context.get_instance(), request, state, skip_same=False)
        request.add_message(u'Workflow status has been changed. New workflow state is: <strong>%s</strong>.' % state)
        return HTTPFound(location=request.fa_url(request.model_name, request.model_id))
    except WorkflowError, msg:
        request.add_message(msg, 'error')
        return HTTPFound(location=request.fa_url(request.model_name, request.model_id))


def change_workflow(context):
    try:
        wf = get_workflow(context.get_instance(), context.get_model().__name__)
    except TypeError:
        wf = None
    if not wf: return
    wf_actions = actions.DropdownActions(id='change_workflow',
            permission='workflow',
            content='%s state' % context.get_instance().workflow_state)

    request = get_current_request()
    states = wf.get_transitions(context.get_instance(), request)
    if not states:
        return None
    for state in states:
        attrs = {'href': "request.fa_url(request.model_name, request.model_id, 'goto_state', state='%s')" % state['to_state']}
        wf_actions.append(actions.TabAction(id=state['to_state'],
            permission='workflow',
            content=state['name'],
            attrs=attrs))
    return wf_actions


def validate_contract_done(content, info):
    """ raise WorkflowError when contract has active CustomerRequests. """
    if [a for a in content.customer_requests if a.active]:
        raise WorkflowError(u'Contract cannot be closed - there are customer requests still open.')


def validate_cr_unachieving(content, info):
    if content.contract and not content.contract.active and info.transition['name'] != 'estimating':
        raise WorkflowError(u'Workflow cannot be changed - related contract is closed.')
