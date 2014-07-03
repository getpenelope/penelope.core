# This Python file uses the following encoding: utf-8
import transaction
import colander

from plone.i18n.normalizer import idnormalizer
from colander import SchemaNode
from deform import ValidationFailure
from deform.widget import CheckboxWidget, TextInputWidget, SequenceWidget
from deform_bootstrap.widget import ChosenSingleWidget, ChosenMultipleWidget
from pyramid.renderers import get_renderer
from pyramid import httpexceptions as exc
from pyramid.i18n import TranslationStringFactory

from penelope.core.models import Project, Group, DBSession, User, CustomerRequest
from penelope.core.models.dashboard import ApplicationACL, Contract
from penelope.core.models.dashboard import Trac, Role, GoogleDoc, Estimation
from penelope.core.lib.widgets import SubmitButton, ResetButton, WizardForm
from penelope.core.fanstatic_resources import wizard as wizard_fanstatic
from penelope.core import PROJECT_ID_BLACKLIST
from penelope.core.notifications import notify_user_with_welcoming_mail

_ = TranslationStringFactory('penelope')


PM_TICKETS = [
 (_(u'Riesami e Verifiche degli Elementi in Ingresso al progetto'),
 _(u"""Questo ticket serve sia per i RIESAMI sia per le VERIFICHE del progetto.
Il RIESAME risponde alle domande HO TUTTI GLI ELEMENTI PER LAVORARE?
STO LAVORANDO SECONDO I REQUISITI DEL CLIENTE? In questo ticket viene
registrato l'avvenuto esame degli elementi iniziali (ad esempio: il
capitolato tecnico) e di tutti gli elementi emersi in corso d'opera (ad
esempio: documenti integrativi). La VERIFICA risponde alle domande HO
FATTO TUTTO QUELLO CHE C’ERA DA FARE? SONO PRONTO AL COLLAUDO? Cioè, per
capire se la produzione è conclusa, verifico che ciò che ho prodotto sia
compatibile con gli input della progettazione. POSSIBILMENTE, CI DOVREBBE
ESSERE UN COMMENT CON L'ELENCO DEI DOCUMENTI CONSULTATI, E UN COMMENT PER
OGNI FASE DI VERIFICA. TECNICAMENTE, QUESTO TICKET ANDREBBE CHIUSO PRIMA
DI PROCEDERE ALLA VALIDAZIONE DEL PROGETTO."""),
  'verification'),

 (_(u'Validazione del progetto'),
 _(u"""Questo ticket serve per la VALIDAZIONE, step finale del ciclo
produttivo, prima della consegna, ovvero la registrazione del fatto che
HO COLLAUDATO IL PRODOTTO IN UN CASO D’USO REALE E CI METTO LA FIRMA! La
validazione delle singole funzionalità avviene a livello di ticket. Questo
ticket viene completato (chiuso) per registrare l'avvenuta validazione del
progetto nel suo assieme. """),
 'verification'),

 (_(u'project management'), u'', 'task'),

 (_(u'incontri con il cliente'), u'', 'task'),

 (_(u'Punto interno con/tra sviluppatori'), u'', 'task'),

 (_(u'Riesame documentazione di progetto (verification)'), u'', 'verification'),

 (_(u'Gestione progetto su Penelope'), u'','task')]


class Definition(colander.Schema):

    def check_project_id(value):
        project_id = idnormalizer.normalize(value)
        project = DBSession().query(Project).get(project_id)
        if value.lower() in PROJECT_ID_BLACKLIST or project:
            return _('${project_id} is a restricted name or already exists! '
                     'Please choose another project name or provide unique ID!',
                     mapping={'project_id': value})
        else:
            return True

    project_name = SchemaNode(typ=colander.String(),
                              widget=TextInputWidget(css_class='input-xlarge',
                                                     placeholder=u'Project name'),
                              missing=colander.required,
                              validator=colander.All(colander.Length(max=20),
                                                     colander.Function(check_project_id)),
                              title=u'')
    trac_name = SchemaNode(typ=colander.String(),
                           widget=TextInputWidget(css_class='input-xxlarge',
                                                  placeholder=u"Short name. "\
                                          "It will appear in email's subject"),
                           missing=None,
                           title=u'')


class GoogleDocsSchema(colander.SequenceSchema):
    class GoogleDocSchema(colander.Schema):
        name = SchemaNode(typ=colander.String(),
                          widget=TextInputWidget(css_class='input-xlarge',
                                                 validator=colander.
                                                               Length(max=20),
                                                 placeholder=u'Enter google '
                                                             'doc name'),
                          missing=colander.required,
                          title=u'')
        uri = SchemaNode(typ=colander.String(),
                         widget=TextInputWidget(css_class='input-xxlarge',
                                                placeholder=u'Paste your '
                                                'google docs folder'),
                         missing=colander.required,
                         title=u'')
        share_with_customer = SchemaNode(typ=colander.Boolean(),
                                         widget=CheckboxWidget(),
                                         missing=None,
                                         title=u'Share with the customer')

    google_doc = GoogleDocSchema(title='')


class UsersSchema(colander.SequenceSchema):
    class UserSchema(colander.Schema):
        usernames = SchemaNode(colander.Set(),
                               widget=ChosenMultipleWidget(placeholder=
                                                           u'Select people'),
                               missing=colander.required,
                               title=u'')
        role = SchemaNode(typ=colander.String(),
                          widget=ChosenSingleWidget(),
                          missing=colander.required,
                          title=u'role')

    user = UserSchema(title='')


class NewUsersSchema(colander.SequenceSchema):
    class NewUserSchema(colander.Schema):
        def unusedEmail(value):
            user = DBSession.query(User.id).filter(User.email == value).first()
            if user:
                return "email '%s' is already associated to another user" % \
                                                                         value
            else:
                return True

        fullname = SchemaNode(typ=colander.String(),
                              widget=TextInputWidget(placeholder=u'Fullname'),
                              missing=colander.required,
                              title=u'')
        email = SchemaNode(typ=colander.String(),
                           widget=TextInputWidget(placeholder=u'E-mail'),
                           missing=colander.required,
                           validator=colander.Function(unusedEmail, ''),
                           title=u'')
        role = SchemaNode(typ=colander.String(),
                          widget=ChosenSingleWidget(),
                          missing=colander.required,
                          title=u'Role')
        send_email_howto = SchemaNode(typ=colander.Boolean(),
                                      widget=CheckboxWidget(),
                                      missing=None,
                                      title=u'Send e-mail')

    new_user = NewUserSchema(title='')


class Milestones(colander.SequenceSchema):
    class Milestone(colander.Schema):
        title = SchemaNode(typ=colander.String(),
                           widget=TextInputWidget(placeholder=u'Title'),
                           missing=colander.required,
                           title=u'')
        due_date = SchemaNode(typ=colander.Date(),
                              missing=colander.required,
                              title=u'Due date')

    milestone = Milestone(title='')


class CustomerRequests(colander.SequenceSchema):
    class CustomerRequest(colander.Schema):
          """
              #BBB specify that junior & co wants days
          """
          title = SchemaNode(typ=colander.String(),
                             widget=TextInputWidget(placeholder=u'Title, '
                                                    'the customer wants...'),
                             missing=colander.required,
                             title=u'')
          junior = SchemaNode(typ=colander.Decimal(),
                              widget=TextInputWidget(css_class='input-mini',
                                                     placeholder=u'Junior'),
                              missing=None,
                              title=u'')
          senior = SchemaNode(typ=colander.Decimal(),
                              widget=TextInputWidget(css_class='input-mini',
                                                     placeholder=u'Senior'),
                              missing=None,
                              title=u'')
          graphic = SchemaNode(typ=colander.Decimal(),
                               widget=TextInputWidget(css_class='input-mini',
                                                      placeholder=u'Graphic'
                                                      ),
                               missing=None,
                               title=u'')
          pm = SchemaNode(typ=colander.Decimal(),
                          widget=TextInputWidget(css_class='input-mini',
                                                 placeholder=u'PM'),
                          missing=None,
                          title=u'')
          architect = SchemaNode(typ=colander.Decimal(),
                                 widget=TextInputWidget(css_class='input-mini',
                                                        placeholder=u'Arch.'),
                                 missing=None,
                                 title=u'')
          tester = SchemaNode(typ=colander.Decimal(),
                              widget=TextInputWidget(css_class='input-mini',
                                                     placeholder=u'Tester'),
                              missing=None,
                              title=u'')
          ticket = SchemaNode(typ=colander.Boolean(),
                              widget=CheckboxWidget(),
                              missing=None,
                              title=u'Create related ticket')

    customer_request = CustomerRequest(title='')


class CRperContracts(colander.MappingSchema):
    class Contract(colander.Schema):
          name = SchemaNode(typ=colander.String(),
                             widget=TextInputWidget(placeholder=u'Contract name'),
                             missing=colander.required,
                             title=u'')
          contract_number = SchemaNode(typ=colander.String(),
                             widget=TextInputWidget(placeholder=u'Contract '
                                                    'number'),
                             missing=None,
                             title=u'')
          days = SchemaNode(typ=colander.Decimal(),
                              widget=TextInputWidget(css_class='input-mini',
                                                     placeholder=u'Days'),
                              missing=None,
                              title=u'')
          amount = SchemaNode(typ=colander.Decimal(),
                              widget=TextInputWidget(css_class='input-mini',
                                                     placeholder=u'amount in EUR'),
                              missing=None,
                              title=u'')
          start_date = SchemaNode(typ=colander.Date(),
                              missing=None,
                              title=u'Start date')
          end_date = SchemaNode(typ=colander.Date(),
                              missing=None,
                              title=u'End date')

    customer_requests = CustomerRequests(missing=None,
            description=u'Following CRs and related tickets will be created only if you assign a budget to it. CRs without a budget will be skipped.')
    contract = Contract(name='',)


class WizardSchema(colander.Schema):
    project = Definition()
    google_docs = GoogleDocsSchema(missing=None)
    users = UsersSchema(missing=None)
    new_users = NewUsersSchema(missing=None)
    milestones = Milestones(missing=None)
    contracts = CRperContracts(missing=None)


class Wizard(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def render(self):
        result = {}
        result['main_template'] = get_renderer(
                'penelope.core:skins/main_template.pt').implementation()
        result['main'] = get_renderer(
                'penelope.core.forms:templates/master.pt').implementation()

        schema = WizardSchema().clone()
        wizard_fanstatic.need()
        form = WizardForm(schema,
                          action=self.request.current_route_url(),
                          formid='wizard',
                          method='POST',
                          buttons=[
                                 SubmitButton(title=u'Submit'),
                                 ResetButton(title=u'Reset'),
                          ])
        form['new_users'].widget = SequenceWidget()
        form['users'].widget = SequenceWidget(min_len=1)

        users = DBSession.query(User).order_by(User.fullname)
        form['users']['user']['usernames'].widget.values = [('', '')] + \
                                      [(str(u.id), u.fullname) for u in users]

        roles = DBSession.query(Role).order_by(Role.name)
        form['users']['user']['role'].widget.values = [('', '')] + \
                                 [(str(role.id), role.name) for role in roles]
        form['new_users']['new_user']['role'].widget.values = [('', '')] + \
                [(str(role.id), role.name) for role in roles]

        form['milestones'].widget = SequenceWidget(min_len=1)
        form['contracts'].title = ''
        form['contracts']['customer_requests'].widget = SequenceWidget(min_len=3)

        controls = self.request.POST.items()
        if controls != []:
            try:
                appstruct = form.validate(controls)
                self.handle_save(form, appstruct)
            except ValidationFailure as e:
                result['form'] = e.render()
                return result

        appstruct = {}
        appstruct['contracts'] ={'customer_requests': []}
        appstruct['contracts']['customer_requests'].append({'ticket': True,
                                                            'title': u'Project management'})
        appstruct['contracts']['customer_requests'].append({'ticket': True,
                                                            'title': u'Analisi'})
        appstruct['contracts']['customer_requests'].append({'ticket': True,
                                                            'title': u'Supporto'})
        result['form'] = form.render(appstruct=appstruct)
        return result

    def handle_save(self, form, appstruct):
        """ The main handle method for the wizard. """
        customer = self.context.get_instance()

        # create new users
        recipients = []
        groups = {}
        for newuser in appstruct['new_users']:
            user = User(fullname=newuser['fullname'], email=newuser['email'])
            if not newuser['role'] in groups:
                groups[newuser['role']] = []
            groups[newuser['role']].append(user)
            if newuser['send_email_howto']:
                recipients.append(newuser['email'])

        for recipient in recipients:
            notify_user_with_welcoming_mail(recipient)

        #create project and set manager
        manager = self.request.authenticated_user
        project = Project(name=appstruct['project']['project_name'],
                          manager=manager)

        #set groups
        for g in appstruct['users']:
            if not g['role'] in groups:
                groups[g['role']] = []
            for u in g['usernames']:
                user = DBSession.query(User).get(u)
                groups[g['role']].append(user)

        for rolename, users in groups.items():
            role = DBSession.query(Role).filter(Role.name == rolename).one()
            group = Group(roles=[role, ], users=users)
            project.add_group(group)

        #create contract with cr
        crs = appstruct['contracts']['customer_requests']
        co =  appstruct['contracts']['contract']
        contract = Contract(**co)
        contract.project_id = project.id

        #create CR
        tickets = []
        for cr in crs:
            customer_request = CustomerRequest(name=cr['title'])
            person_types = {
                'junior': 'Junior',
                'senior': 'Senior',
                'graphic': 'Graphic',
                'pm': 'Project manager',
                'architect': 'Architect',
                'tester': 'Tester'
            }
            for key, value in person_types.items():
                if cr[key]:
                    Estimation(person_type=value,
                              days=cr[key],
                              customer_request=customer_request)
                    customer_request.workflow_state = 'estimated'

            if not customer_request.estimations:
                # skip CR creation if there are no estimations/budget assigned
                continue

            project.add_customer_request(customer_request)
            customer_request.contract = contract

            DBSession().flush() # get customer_request.id

            if cr['title'] == 'Project management':
                for summary, description, ticket_type in PM_TICKETS:
                    tickets += [{ 'summary': summary,
                                  'description': description,
                                  'customerrequest': customer_request.id,
                                  'reporter': manager.email,
                                  'type': ticket_type,
                                  'priority': 'major',
                                  'sensitive': '1',
                                  'milestone': 'Backlog',
                                  'owner': manager.email}]

            elif cr['ticket']:
                tickets += [{'summary': cr['title'],
                            'customerrequest': customer_request.id,
                            'reporter': manager.email,
                            'type': 'task',
                            'priority': 'major',
                            'milestone': 'Backlog',
                            'owner': manager.email}]

        #create google docs/folders
        for app_definition in appstruct['google_docs']:
            app = GoogleDoc(name=app_definition['name'],
                            api_uri=app_definition['uri'])
            if app_definition['share_with_customer']:
                acl = ApplicationACL(role_id='customer',
                                     permission_name='view')
                acl.project = app
            project.add_application(app)
        milestones = appstruct['milestones']

        #create trac
        trac = Trac(name="Trac for %s" % appstruct['project']['project_name'])
        if appstruct['project']['trac_name']:
            trac_project_name = appstruct['project']['trac_name']
        else:
            trac_project_name = appstruct['project']['project_name']

        customer.add_project(project)
        customer_id = customer.id
        project_name = project.name
        trac.api_uri = 'trac://' # this will prevent firing event
        project.add_application(trac)
        t = transaction.get()
        t.commit()

        transaction.begin()
        from penelope.trac.populate import add_trac_to_project
        project = DBSession().query(Project).filter_by(name=project_name).one()
        for trac in project.tracs:
            add_trac_to_project(trac,
                                milestones=milestones, tickets=tickets,
                                project_name=trac_project_name)
        DBSession().merge(trac)
        t = transaction.get()
        t.commit()
        raise exc.HTTPFound(location=self.request.fa_url('Customer',
                                                         customer_id))
