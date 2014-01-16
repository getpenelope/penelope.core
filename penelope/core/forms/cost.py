# -*- coding: utf-8 -*-
from penelope.core.forms import ModelView


def configurate(config):
    config.formalchemy_model_view('admin',
        request_method='POST',
        permission='delete',
        name='delete',
        attr='delete',
        renderer='fa.bootstrap:templates/admin/edit.pt',
        model='penelope.core.models.dashboard.Cost',
        view=CostModelView)


class CostModelView(ModelView):

    def delete(self):
        return self.force_delete()
