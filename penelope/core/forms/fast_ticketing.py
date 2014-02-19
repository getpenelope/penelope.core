import colander
import deform

from deform import ValidationFailure
from deform_bootstrap.widget import ChosenSingleWidget
from pyramid.renderers import get_renderer
from pyramid import httpexceptions as exc

from penelope.core.lib.widgets import SubmitButton, ResetButton, WizardForm
from penelope.core.fanstatic_resources import fastticketing as fastticketing_fanstatic
from penelope.core.models.tickets import ticket_store


class Tickets(colander.SequenceSchema):
    class Ticket(colander.Schema):
          """
              summary: entered by user
              description: entered by user in wiki syntax
              customerrequest: the context,
              reporter: user's email,
              type: 'task',
              priority: 'major',
              milestone: 'Backlog' (choosen for the available ones in trac?)
              owner: user's email
          """
          summary = colander.SchemaNode(typ=colander.String(),
                            widget=deform.widget.TextInputWidget(placeholder=u"Enter the ticket's title"),
                            missing=colander.required,
                            title=u'Summary')
          description = colander.SchemaNode(
                            colander.String(),
                            widget=deform.widget.TextAreaWidget(
                                  cols=60,
                                  rows=5),
                            missing=colander.required,
                            title=u'Description',
                            description=u'use wiki syntax')
          owner = colander.SchemaNode(typ=colander.String(),
                            widget=ChosenSingleWidget(placeholder= u'Select the pal to assign to'),
                            missing=colander.required,
                            title=u'Owner')

    ticket = Ticket(title='')


class FastTicketingSchema(colander.Schema):
    tickets = Tickets()


class FastTicketing(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def render(self):
        result = {}
        result['main_template'] = get_renderer(
               'penelope.core:skins/main_template.pt').implementation()
        result['main'] = get_renderer(
               'penelope.core.forms:templates/master.pt').implementation()

        schema = FastTicketingSchema().clone()
        fastticketing_fanstatic.need()
        form = WizardForm(schema,
                          action=self.request.current_route_url(),
                          formid='fastticketing',
                          method='POST',
                          buttons=[
                                 SubmitButton(title=u'Submit'),
                                 ResetButton(title=u'Reset'),
                          ])
        form.bootstrap_form_style = ''
        form['tickets'].widget = deform.widget.SequenceWidget(min_len=1)

        users = set()
        project = self.context.get_instance().project
        for g in getattr(project, 'groups', []):
          for u in g.users:
            users.add(u)
        users.add(project.manager)
        form['tickets']['ticket']['owner'].widget.values = [('', '')] + \
                                      [(str(u.id), u.fullname) for u in list(users)]

        controls = self.request.POST.items()
        if controls != []:
            try:
                appstruct = form.validate(controls)
                self.handle_save(form, appstruct)
            except ValidationFailure as e:
                result['form'] = e.render()
                return result

        result['form'] = form.render()
        return result

    def handle_save(self, form, appstruct):
        try:
            customerrequest = self.context.get_instance()
            customerrequest_id = customerrequest.id
            user = self.request.authenticated_user
            ticket_store.add_tickets(project = self.request.model_instance.project, 
                    customerrequest = customerrequest,
                    tickets = appstruct['tickets'],
                    reporter = user,
                    notify=True)

        except Exception, e:
            self.request.add_message(u'There was an exception: %s' % e, type='danger')
            raise ValidationFailure(form, appstruct, None)

        raise exc.HTTPFound(location=self.request.fa_url('CustomerRequest',
            customerrequest_id))
