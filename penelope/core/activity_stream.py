import transaction
import redis
import pretty

from datetime import datetime
from time import sleep
from socketio.namespace import BaseNamespace
from penelope.core.models.dashboard import Activity
from penelope.core.models.dbsession import DBSession


class FeedlyNamespace(BaseNamespace):

    def listener(self):
        r = redis.StrictRedis()
        r = r.pubsub()
        r.subscribe('penelope:notifications:%s' % self.session['user_id']) # feedly pubsub key

        for m in r.listen():
            if m['type'] == 'message':
                sleep(1) # wait for the commit; to be fixed
                count_unseen, activities = self._get_activities_()
                self.emit("activities", {'count_unseen':count_unseen,
                                         'activities': activities})

    def _get_activities_(self):
        session = DBSession()
        base_query = session.query(Activity)\
                            .filter_by(user_id=self.session['user_id'])
        count_unseen = base_query.filter_by(seen_at=None).count()
        activities = base_query.order_by(Activity.created_at.desc()).limit(5)

        response = []
        for activity in activities:
            response.append({'message': activity.message,
                             'unseen': activity.unseen,
                             'absolute_path': activity.absolute_path,
                             'created_by': activity.created_by,
                             'created_at': pretty.date(activity.created_at)})

        transaction.commit()
        return count_unseen, response

    def on_join(self, data):
        self.session['user_id'] = data['user_id']
        self.spawn(self.listener)
        count_unseen, activities = self._get_activities_()
        self.emit("activities", {'count_unseen':count_unseen,
                                 'activities': activities})

    def on_mark_all_seen(self, data):
        user_id = data['user_id']
        session = DBSession()
        unseen = session.query(Activity)\
                        .filter_by(user_id=user_id)\
                        .filter_by(seen_at=None)
        now = datetime.now()
        for a in unseen:
            a.seen_at = now
        transaction.commit()
        r = redis.StrictRedis()
        r.publish('penelope:notifications:%s' % user_id, True)

    def recv_disconnect(self):
        self.disconnect(silent=True)


def add_activity(user_ids, message, absolute_path, created_by=None):
    if created_by is None:
        created_by = 'penelopedev@redturtle.it'

    r = redis.StrictRedis()
    session = DBSession()
    for user_id in user_ids:
        activity = Activity(message=message,
                            created_at=datetime.now(),
                            user_id=user_id,
                            absolute_path=absolute_path,
                            created_by=created_by)

        session.add(activity)
        r.publish('penelope:notifications:%s' % user_id, True)
    transaction.commit()
