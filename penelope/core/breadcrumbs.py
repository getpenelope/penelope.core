import zope.component
from zope.interface import Interface
from fa.bootstrap import actions

from penelope.core.interfaces import IBreadcrumbs, IReportView
from penelope.core.models.interfaces import IPorModel, IProjectRelated, IKanbanBoard


gsm = zope.component.getGlobalSiteManager()


class PORBreadcrumbAction(actions.BreadcrumbAction):
    body = u'''<li tal:attributes="class action.isActive(request) and \'active\' or \'\'">
                    <a tal:attributes="%(attributes)s">${content}</a>
                    <span tal:condition="not action.isActive(request)" class="divider">/</span>
               </li>'''


class BreadcrumbRenderer(object):
    def __init__(self, context):
        self.context = context
        self.breadcrumbs = actions.actions.Actions()
        self.breadcrumbs.append(PORBreadcrumbAction('home',
            content='Home',
            attrs=dict(href="request.application_url")))

    @property
    def current_id(self):
        if self.context.request:
            return self.context.request.view_name or getattr(self.context.request, 'model_name', None)
        else:
            return ''

    @property
    def current_title(self):
        return self.current_id.replace('_', ' ').title()

    def render(self, request):
        if self.current_id:
            self.breadcrumbs.append(PORBreadcrumbAction(self.current_id,
                content=self.current_title,
                attrs=dict(href="request.path_url")))
        if len(self.breadcrumbs)>1:
            return self.breadcrumbs.render(request)
        else:
            return ''

gsm.registerAdapter(BreadcrumbRenderer, (Interface,), IBreadcrumbs)


class BreadcrumbReportRenderer(BreadcrumbRenderer):
    def render(self, request):
        if self.current_id != 'index':
            self.breadcrumbs.append(PORBreadcrumbAction('reports',
                content='Reports',
                attrs=dict(href="'%s/reports/index' % request.application_url")))
        return super(BreadcrumbReportRenderer, self).render(request)

gsm.registerAdapter(BreadcrumbReportRenderer, (IReportView,), IBreadcrumbs)


class BreadcrumbCrudRenderer(BreadcrumbRenderer):
    @property
    def current_id(self):
        return self.context.id

    @property
    def current_title(self):
        return unicode(self.context)

gsm.registerAdapter(BreadcrumbCrudRenderer, (IPorModel,), IBreadcrumbs)


class BreadcrumbKanbanRenderer(BreadcrumbCrudRenderer):
    def render(self, request):
        self.breadcrumbs.append(PORBreadcrumbAction('Kanbanboard',
            content='Kanbanboard',
            attrs=dict(href="'%s/admin/KanbanBoard' % request.application_url")))
        return super(BreadcrumbKanbanRenderer, self).render(request)

gsm.registerAdapter(BreadcrumbKanbanRenderer, (IKanbanBoard,), IBreadcrumbs)


class BreadcrumbProjectRelatedRenderer(BreadcrumbRenderer):
    def render(self, request):
        project = self.context.project

        if project.customer:
            self.breadcrumbs.append(PORBreadcrumbAction(project.customer.id,
                content=unicode(project.customer),
                attrs=dict(href="request.fa_url('Customer','%s')" % project.customer.id)))

        if project != self.context:
            self.breadcrumbs.append(PORBreadcrumbAction(project.id,
                content=unicode(project.name),
                attrs=dict(href="request.fa_url('Project','%s')" % project.id)))

            if request.model_name in ('CustomerRequest','Application','Group'):
                model_name = self.context.project_related_label
                self.breadcrumbs.append(PORBreadcrumbAction(model_name,
                    content=unicode(model_name),
                    attrs=dict(href="request.fa_url('Project','%s', '%s')" % (project.id, self.context.project_related_id))
                ))

        if project == self.context:
            name = project.name
        else:
            name = unicode(self.context)
        self.breadcrumbs.append(PORBreadcrumbAction(self.context.id,
            content=name,
            attrs=dict(href="request.path_url")))

        return self.breadcrumbs.render(request)

gsm.registerAdapter(BreadcrumbProjectRelatedRenderer, (IProjectRelated,), IBreadcrumbs)

