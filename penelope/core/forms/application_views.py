import zope.component
import feedparser
import datetime, time

from zope.interface import Interface
from pyramid.renderers import get_renderer

from penelope.core.interfaces import IApplicationView
from penelope.core.models.interfaces import ITrac, IApplication, ITracReport, IGoogleDocs
from penelope.core.gdata.views import get_google_document

gsm = zope.component.getGlobalSiteManager()


class UnknownApplicationRenderer(object):
    def __init__(self, application, context, request):
        self.application = application
        self.context = context
        self.request = request

    def render(self):
        result = {}
        result.update(application=self.application,
            context=self.context,
            template=get_renderer('penelope.core.forms:templates/application_generic_view.pt').implementation(),
            request=self.request)
        return result

gsm.registerAdapter(UnknownApplicationRenderer, (IApplication, Interface, Interface), IApplicationView)


class GoogleDocsRenderer(UnknownApplicationRenderer):
    def render(self):
        result = {}
        result.update(application=self.application,
            context=self.context,
            request=self.request)

        response = get_google_document(self.context, self.request, uri=self.application.api_uri)
        result.update(**response)

        def convert_date(node):
            if not node:
                return ''
            else:
                date = node.text
            date = date[:19]
            return datetime.datetime.fromtimestamp(time.mktime(
                        time.strptime(date,'%Y-%m-%dT%H:%M:%S'))).strftime('%Y-%m-%d %H:%M:%S')

        if 'folder' in response.keys():
            template = get_renderer('penelope.core.forms:templates/application_googlefolder_view.pt').implementation()
            result.update(template=template)
            result.update(convert_date=convert_date)

        elif 'document' in response.keys():
            if response['document']:
                doc_url = response['document'].get_html_link().href.replace('/edit', '/preview')
            else:
                doc_url = ''
            template = get_renderer('penelope.core.forms:templates/application_googledocument_view.pt').implementation()
            result.update(template=template, doc_url=doc_url)

        else:
            template = get_renderer('penelope.core.forms:templates/application_googledocument_view.pt').implementation()
            result.update(template=template, doc_url='')

        return result

gsm.registerAdapter(GoogleDocsRenderer, (IGoogleDocs, Interface, Interface), IApplicationView)


class TracRenderer(UnknownApplicationRenderer): pass

gsm.registerAdapter(TracRenderer, (ITrac, Interface, Interface), IApplicationView)

class TracReportRenderer(UnknownApplicationRenderer):
    def render(self):
        result = {}
        cookie = self.request.headers.get('Cookie')
        url = self.application.application_uri(request=self.request)
        rss_url = '%s%sasc=1&format=rss' % (url, '?' in url and '&' or '?')
        feed = feedparser.parse(rss_url, request_headers={'Cookie': cookie})
        result.update(application=self.application,
            context=self.context,
            feed=feed,
            template=get_renderer('penelope.core.forms:templates/application_trac_report.pt').implementation(),
            request=self.request)
        return result

gsm.registerAdapter(TracReportRenderer, (ITracReport, Interface, Interface), IApplicationView)
