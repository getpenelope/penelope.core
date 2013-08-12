# -*- coding: utf-8 -*-

from webhelpers.html import HTML


def get_application_icon(request, application):
    return {
            'google docs': '/static/images/application_type_google.png',
            'trac': '/static/images/application_type_trac.png',
            'trac report': '/static/images/application_type_trac_report.png',
            'svn': '/static/images/application_type_svn.png',
            }.get(application.application_type, None)


def get_application_link(request, application):
    if application.application_type == 'trac':
        return application.api_uri

    return '%s/admin/Application/%s' % (request.application_url, application.id)



def render_application_icon(request, application):
    return HTML.IMG(src=get_application_icon(request, application),
                    width="16",
                    height="16")

