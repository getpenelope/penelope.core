# -*- coding: utf-8 -*-

def get_application_link(request, application):
    if application.application_type == 'trac':
        return application.api_uri

    return '%s/admin/Application/%s' % (request.application_url, application.id)
