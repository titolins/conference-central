#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime
from datetime import time
from datetime import date

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceUpdateForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize
from models import Session
from models import SessionForm
from models import SessionUpdateForm
from models import SessionForms
from models import Speaker
from models import SpeakerForm
from models import SpeakerUpdateForm
from models import SpeakerForms

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
FEATURED_SPEAKER_TPL = ('You should not miss the following sessions by our '
                    'featured speaker %s: %s')
#MEMCACHE_SPEAKER_KEY = "FEATURED_SPEAKER"
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

SESSION_DEFAULTS = {
    "highlights": [ "Default", "Highlight" ],
    "speaker": "john doe",
    "duration": 0,
    "typeOfSession": u'session type',
}

SPEAKER_DEFAULTS = {
    "specialties": [ "Default", "Specialty" ],
    "city": "Default City",
    "country": "Default Country",
    "languages": [ "Default", "Language" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

SESSION_FIELDS = {
        'HIGHLIGHT': 'highlights',
        'TYPE': 'typeOfSession',
        'DATE': 'date',
        'START_TIME': 'startTime',
        }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_GET_BY_TYPE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    sessionType=messages.StringField(2, required=True),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_UPDATE_REQUEST = endpoints.ResourceContainer(
    ConferenceUpdateForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_POST_UPDATE_REQUEST = endpoints.ResourceContainer(
    SessionUpdateForm,
    websafeSessionKey=messages.StringField(1),
)

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1, required=True),
)
'''
SPEAKER_POST_REQUEST = endpoints.ResourceContainer(
    SpeakerForm,
    websafeSessionKey=messages.StringField(1),
)
'''

SPEAKER_POST_UPDATE_REQUEST = endpoints.ResourceContainer(
    SpeakerUpdateForm,
    websafeSpeakerKey=messages.StringField(1),
)

ADD_SESSION_POST_REQUEST = endpoints.ResourceContainer(
        websafeSessionKey=messages.StringField(1, required=True),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[
        WEB_CLIENT_ID,
        API_EXPLORER_CLIENT_ID,
        ANDROID_CLIENT_ID,
        IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""


# - - - Speaker objects - - - - - - - - - - - - - - - - -

# Speaker's life flow will be controlled by the session they're attached to.
# They may be updated, however, in order for the authorized user to insert
# attributes other than it's name.


    def _createSpeakerObject(self, request):
        """method responsible for the actual creation of the speaker object"""
        # First we check to see if the speaker already exists
        sp = Speaker.query(Speaker.name==request['speaker']).get()
        s_key = ndb.Key(urlsafe=request['websafeSessionKey'])
        conf_key = ndb.Key(urlsafe=request['websafeConferenceKey'])
        if sp:
            # if it does, we simply append the newly created session key to it
            sp.sessions.append(s_key)
            sp.put()
            self._checkFeatured(sp, conf_key)
            return self._copySpeakerToForm(sp, s_key.get().name)

        # otherwise, we create a new speaker entity
        s = s_key.get()
        data = {
                'name': request['speaker'],
                'sessions': [s_key,],
                }

        # sets the default options
        for df in SPEAKER_DEFAULTS:
            data[df] = SPEAKER_DEFAULTS[df]
            request[df] = SPEAKER_DEFAULTS[df]

        # generate the speaker id based on the session key
        sp_id = Session.allocate_ids(size=1)[0]

        # create speaker key
        sp_key = ndb.Key(Speaker, sp_id)
        data['key'] = sp_key

        # add session id to object data and form
        #data['sessionId'] = request['sessionId'] = s.key.id()

        # save to db and return
        Speaker(**data).put()
        sp = sp_key.get()
        self._checkFeatured(sp, conf_key)
        return self._copySpeakerToForm(sp, s.name)


    def _checkFeatured(self, speaker, conferenceKey):
        '''
        Checks if a speaker should be considered featured within a given
        conference. A speaker will be considered a featured speaker if there is
        more than one session by such speaker in the conference.
        '''
        # initialize the counter
        count = 0
        # get the speaker sessions and iterate them
        sessions = []
        for session in ndb.get_multi(speaker.sessions):
            # grabs the session conference and checks if it's the same
            # conference of the newly created session (if so, increments the
            # counter).
            sessionConference = session.key.parent().get()
            if conferenceKey == sessionConference.key:
                count += 1
                sessions.append(session.name)
        # if the counter is greater than 1 (meaning the speaker has another
        # session in the conference, besides the newly created session), it is
        # a featured speaker and shall be added to memcache.
        if count > 1:
            taskqueue.add(
                    params={
                        'speaker_name': speaker.name,
                        'websafeConferenceKey': conferenceKey.urlsafe(),
                        'sessions': ', '.join(session for session in sessions),
                    },
                    url='/tasks/set_featured_speaker')
        else:
            return None


    def _copySpeakerToForm(self, speaker, displayName):
        """Copy Speaker fields from request to SpeakerForm"""
        spForm = SpeakerForm()
        for field in spForm.all_fields():
            if field.name == "sessions":
                sessions = []
                for session in getattr(speaker, "sessions"):
                    sessions.append(session.urlsafe())
                setattr(spForm, field.name, sessions)
            elif hasattr(speaker, field.name):
                setattr(spForm, field.name, getattr(speaker, field.name))
            elif field.name == "websafeKey":
                setattr(spForm, field.name, speaker.key.urlsafe())
        if displayName:
            setattr(spForm, 'sessionDisplayName', displayName)
        spForm.check_initialized()
        return spForm


    @endpoints.method(SESSION_GET_REQUEST, SpeakerForm,
            path='session/{websafeSessionKey}/speaker',
            http_method='GET', name='getSessionSpeaker')
    def getSessionSpeaker(self, request):
        """Get speaker associated with a given session"""
        s_key = ndb.Key(urlsafe=request.websafeSessionKey)
        s = s_key.get()
        if not s:
            raise endpoints.NotFoundException(
                'No session found with key: %s'
                 % request.websafeSessionKey)
        speaker = Speaker.query(Speaker.name==s.speaker).get()
        return self._copySpeakerToForm(speaker, s.name)


    @endpoints.method(SPEAKER_POST_UPDATE_REQUEST, SpeakerForm,
        path='speaker/{websafeSpeakerKey}',
        http_method='PUT', name='updateSpeaker')
    def updateSpeaker(self, request):
        """Update speaker w/provided fields & return w/updated info."""
        return self._updateSpeakerObject(request)


    @ndb.transactional()
    def _updateSpeakerObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy Speaker/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)\
                for field in request.all_fields()}

        # update existing speaker
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        # check that conference exists
        if not speaker:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s' % request.websafeSpeakerKey)
        session = speaker.key.parent().get()
        conf = session.key.parent().get()

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the speaker of the session.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from SpeakerUpdateForm to Speaker object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # write to speaker object
                setattr(speaker, field.name, data)
        speaker.put()
        return self._copySpeakerToForm(speaker, getattr(session, 'name'))


    @staticmethod
    def _cacheFeaturedSpeaker(speaker_name, websafeConferenceKey, sessions):
        featured = FEATURED_SPEAKER_TPL % (speaker_name, sessions,)
        memcache.set(websafeConferenceKey, featured)


    @endpoints.method(CONF_GET_REQUEST, StringMessage,
            path='get_featured_speaker',
            http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return featured speaker from memcache."""
        return StringMessage(
                data=memcache.get(request.websafeConferenceKey) or "")


# - - - Session objects - - - - - - - - - - - - - - - - -


    def _copySessionToForm(self, session, displayName):
        """Copy session fields to SessionForm."""
        sessionForm = SessionForm()
        for field in sessionForm.all_fields():
            if hasattr(session, field.name):
                # converts time and date objects to string
                if field.name in ["date", "startTime"]:
                    setattr(
                            sessionForm,
                            field.name,
                            str(getattr(session, field.name)))
                else:
                    setattr(
                            sessionForm,
                            field.name,
                            getattr(session, field.name))
            elif field.name == "websafeKey":
                setattr(sessionForm, field.name, session.key.urlsafe())
        if displayName:
            setattr(sessionForm, 'conferenceDisplayName', displayName)
        sessionForm.check_initialized()
        return sessionForm


    @endpoints.method(SESSION_POST_REQUEST, SessionForm,
            path='conference/{websafeConferenceKey}/session',
            http_method='PUT', name='createSession')
    def createSession(self, request):
        """Create a new session object attached to a given conference"""
        return self._createSessionObject(request)


    def _createSessionObject(self, request):
        """Creates a new session object"""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # first see if we have a conference with the given key
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                % request.websafeConferenceKey)
        # then we check if the user accessing the api is authorized to do so
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the conference organizer can create sessions.')
        # and then we check for the only required field for creating a session
        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = { field.name: getattr(request, field.name)\
                for field in request.all_fields() }
        del data['websafeConferenceKey']
        del data['websafeKey']
        del data['conferenceDisplayName']

        # sets default options
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                setattr(request, df, SESSION_DEFAULTS[df])

        # converting date and time objects
        try:
            # we are considering the same format received when of the creation
            # of a new conference
            # e.g.: '2016-02-11T02:00:00.000Z'
            data['date'] = datetime.strptime(
                    data['date'][:10], "%Y-%m-%d").date()
        except (ValueError, TypeError) as e:
            # If no date supplied we just initialize an empty time
            data['date'] = getattr(conf, 'startDate')
            pass
        try:
            # we are considering a regular time format here
            # e.g.: '02:00:00'
            data['startTime'] = datetime.strptime(
                    data['startTime'], "%H:%M:%S").time()
        except (ValueError, TypeError) as e:
            # If no time supplied we just initialize an empty time
            data['startTime'] = time()
            pass

        # generate the session key based on the conference key
        c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        s_id = Session.allocate_ids(
                size=1,
                parent=c_key)[0]

        # create session key
        s_key = ndb.Key(Session, s_id, parent=c_key)
        data['key'] = s_key

        data['conferenceId'] = request.conferenceId = c_key.id()

        # save to db and return
        Session(**data).put()
        # create speaker entity
        speakerRequest = {
                'speaker': request.speaker,
                'websafeSessionKey': s_key.urlsafe(),
                'websafeConferenceKey': c_key.urlsafe(),
                }
        self._createSpeakerObject(speakerRequest)

        return self._copySessionToForm(request, getattr(conf, 'name'))


    @endpoints.method(SESSION_POST_UPDATE_REQUEST, SessionForm,
            path='session/{websafeSessionKey}',
            http_method='PUT', name='updateSession')
    def updateSession(self, request):
        """Update session w/provided fields & return w/updated info."""
        return self._updateSessionObject(request)


    @ndb.transactional()
    def _updateSessionObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy SessionForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)\
                for field in request.all_fields()}

        # update existing session
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()
        # check that conference exists
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % request.websafeSessionKey)
        conf = session.key.parent().get()

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the session.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from SessionUpdateForm to Session object
        for field in request.all_fields():
            #field_data = getattr(request, field.name)
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name == 'date':
                    # we are considering the same format received when of the
                    # creation of a new conference
                    # e.g.: '2016-02-11T02:00:00.000Z'
                    data = datetime.strptime(data[:10], "%Y-%m-%d").date()
                elif field.name == 'startTime':
                    # we are considering a regular time format here
                    # e.g.: '02:00:00'
                    data = datetime.strptime(data, "%H:%M:%S").time()
                # write to session object
                setattr(session, field.name, data)
        session.put()
        return self._copySessionToForm(session, getattr(conf, 'name'))


    @endpoints.method(CONF_GET_REQUEST, SessionForms,
            path='conference/{websafeConferenceKey}/sessions',
            http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Get sessions associated with a given conference"""
        # get the conference key separately -- we'll need it again below
        c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        conf = c_key.get()
        # check if websafeConferenceKey matches a conference
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                 % request.websafeConferenceKey)
        # use the conference key to query for all it's sessions and return them
        # as a SessionForms
        sessions = Session.query(ancestor=c_key)
        return SessionForms(
                items=[
                    self._copySessionToForm(session, getattr(conf, 'name'))\
                            for session in sessions]
                )


    @endpoints.method(CONF_GET_BY_TYPE_REQUEST, SessionForms,
            path='conference/{websafeConferenceKey}/sessions/type',
            http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Get's conference sessions filtered by type"""
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                 % request.websafeConferenceKey)
        sessions = Session.query(ancestor=conf.key).\
                filter(Session.typeOfSession==request.sessionType)
        return SessionForms(
                items=[
                    self._copySessionToForm(session, getattr(conf, 'name'))\
                    for session in sessions]
                )


    @endpoints.method(SPEAKER_GET_REQUEST, SessionForms,
            path='sessions/byspeaker', http_method='GET',
            name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """
        Get sessions given by the speaker specified across all conferences
        """
        # Get speaker by name
        speaker = Speaker.query(Speaker.name==request.speaker).get()
        sessions = []
        # Try to get the speaker sessions. If we have an AttributeError, it's
        # because no speaker was found.
        try:
            sessions = ndb.get_multi(speaker.sessions)
        except AttributeError:
            # No speaker found
            pass
        return SessionForms(
                items=[
                    self._copySessionToForm(
                        session,
                        session.key.parent().get().name
                    )\
                    for session in sessions]
                )


    @endpoints.method(ConferenceQueryForms, SessionForms,
            path='querySessions',
            http_method='POST', name='querySessions')
    def querySessions(self, request):
        """
            API endpoint for enabling session queries to be filtered by any
            number of inequality filters.
        """
        q = Session.query()
        inequality_filters, filters = self._formatAllFilters(request.filters)

        # first, we apply the regular filters
        for f in filters:
            if f['field'] == 'date':
                f['value'] = datetime.strptime(f['value'][:10], "%Y-%m-%d").\
                        date()
            elif f['field'] == 'startTime':
                f['value'] = datetime.strptime(f['value'], "%H:%M:%S").time()
            query = ndb.query.FilterNode(f['field'], f['operator'], f['value'])
            q = q.filter(query)

        # if there is at least one inequality filter, we filter it using ndb
        # and remove it from the list (it should be more efficient than using
        # the _doInequalityFilter method)
        # REMOVED because filtering by datetime.time() and datetime.date()
        # apparently is not supported (BadValueError). For now, we just apply
        # all inequality filters with self._doInequalityFilter method.
        # It shouldn't be as efficient, but at least it works..
        '''
        if len(inequality_filters) > 0:
            f = inequality_filters.pop()
            if f['field'] == 'date':
                f['value'] = datetime.strptime(f['value'][:10], "%Y-%m-%d").\
                        date()
            #elif f['field'] == 'startTime':
            #    f['value'] = datetime.strptime(f['value'], "%H:%M:%S").time()
            query = ndb.query.FilterNode(f['field'], f['operator'], f['value'])
            q = q.filter(query)
        '''
        # creates a python list with all elements not filtered as of yet
        s_list = [o for o in q]
        # In case there are more inequality filters, we filter them in memory.
        # This can be further improved, as the datastore limitation relates to
        # inequality filters on different properties. We are only checking for
        # multiple inequality filters, with disregard of the property it is
        # applied to.
        for in_filter in inequality_filters:
            s_list = self._doInequalityFilter(in_filter, s_list)

        # return a form with all sessions remaining after all filters have
        # been applied.
        return SessionForms(
            items=[self._copySessionToForm(session, "") for session in s_list]
        )


    def _formatAllFilters(self, filters):
        """
            Same as the original self._formatFilter, except it aggregates all
            inequality filters in a list and does not raise an exception in case
            there is more than one inequality filter
        """
        formatted_filters = []
        formatted_inequality_filters = []
        for f in filters:
            filtr = {field.name: getattr(f, field.name)\
                    for field in f.all_fields()}
            try:
                filtr["field"] = SESSION_FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                        "Filter contains invalid field or operator.")
            if filtr["operator"] != "=":
                formatted_inequality_filters.append(filtr)
            else:
                formatted_filters.append(filtr)
        return (formatted_inequality_filters, formatted_filters)


    def _doInequalityFilter(self, f, query):
        """
        Applies inequality filters on memory objects received from a query,
        to bypass DataStore limitations
        """
        op = f['operator']
        if f['field'] == 'date':
            f['value'] = datetime.strptime(f['value'][:10], "%Y-%m-%d").\
                date()
        elif f['field'] == 'startTime':
            f['value'] = datetime.strptime(f['value'], "%H:%M:%S").time()

        if op == '!=':
            return [obj for obj in query \
                    if getattr(obj, f['field']) != f['value']]
        elif op == '>':
            return [obj for obj in query \
                    if getattr(obj, f['field']) > f['value']]
        elif op == '>=':
            return [obj for obj in query \
                    if getattr(obj, f['field']) >= f['value']]
        elif op == '<':
            return [obj for obj in query \
                    if getattr(obj, f['field']) < f['value']]
        elif op == '<=':
            return [obj for obj in query \
                    if getattr(obj, f['field']) <= f['value']]


# - - - Session wishlist - - - - - - - - - - - - - - - - - -

    @endpoints.method(ADD_SESSION_POST_REQUEST, SessionForms,
            path='profile/sessions/delete',
            http_method='PUT', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """Deletes session from authorized user wishlist"""
        prof = self._getProfileFromUser() # get user Profile
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % request.websafeSessionKey)
        if request.websafeSessionKey not in getattr(prof, 'sessionWishlist'):
            raise ConflictException(
                "You do not have this session in your wishlist")
        prof.sessionWishlist.remove(request.websafeSessionKey)
        prof.put()
        sessionKeys = [ndb.Key(urlsafe=websafeSessionKey) for websafeSessionKey
                in getattr(prof, 'sessionWishlist')]
        sessions = ndb.get_multi(sessionKeys)
        return SessionForms(
                items=[
                    self._copySessionToForm(session, '')\
                    for session in sessions]
                )


    @endpoints.method(ADD_SESSION_POST_REQUEST, SessionForms,
            path='profile/sessions',
            http_method='PUT', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Adds a session to the authorized user session wishlist"""
        prof = self._getProfileFromUser() # get user Profile

        # check if the session exists given websafeSessionKey
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % request.websafeSessionKey)
        if request.websafeSessionKey in getattr(prof, 'sessionWishlist'):
            raise ConflictException(
                "You have already added this session to your wishlist")
        prof.sessionWishlist.append(request.websafeSessionKey)
        prof.put()
        sessionKeys = [ndb.Key(urlsafe=websafeSessionKey) for websafeSessionKey
                in getattr(prof, 'sessionWishlist')]
        sessions = ndb.get_multi(sessionKeys)
        return SessionForms(
                items=[
                    self._copySessionToForm(session, '')\
                    for session in sessions]
                )


    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='profile/sessions',
            http_method='GET', name='getSessionWishlist')
    def getSessionWishlist(self, request):
        """ Get the authorized user session wishlist """
        prof = self._getProfileFromUser() # get user Profile
        sessionKeys = [ndb.Key(urlsafe=websafeSessionKey) for websafeSessionKey
                in getattr(prof, 'sessionWishlist')]
        sessions = ndb.get_multi(sessionKeys)
        return SessionForms(
                items=[
                    self._copySessionToForm(session, '')\
                    for session in sessions]
                )


# - - - Conference objects - - - - - - - - - - - - - - - - -


    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create Conference object"""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                    "Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)\
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing
        # (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects.
        # set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(
                    data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(
                    data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        prof = p_key.get()
        try:
            return self._copyConferenceToForm(request, getattr(prof, 'displayName'))
        except AttributeError:
            return self._copyConferenceToForm(request, '')


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)\
                for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_UPDATE_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        try:
            return self._copyConferenceToForm(request, getattr(prof, 'displayName'))
        except AttributeError:
            return self._copyConferenceToForm(request, '')


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[
                self._copyConferenceToForm(conf, getattr(prof, 'displayName'))\
                        for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(
                    filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)\
                    for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                        "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed on a
                # different field before track the field on which the
                # inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                            "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId))\
                for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[
                    self._copyConferenceToForm(
                        conf,
                        names[conf.organizerUserId])\
                    for conf in conferences]
        )



# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(
                        TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if
        non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(
                data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck)\
                for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId)\
                for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
                items=[
                    self._copyConferenceToForm(
                        conf,
                        names[conf.organizerUserId])\
                    for conf in conferences]
                )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground"""
        q = Session.query().\
            filter(Session.startTime<datetime.strptime(
                "19:00:00", "%H:%M:%S").time()).\
            order(Session.startTime)
        q = q.filter(Session.typeOfSession!="workshop")
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        #q = q.filter(Session.typeOfSession!="workshop")
        #q = q.filter(Session.startTime<datetime.strptime("19:00:00", "%H:%M:%S").time())

        return SessionForms(
            items=[self._copySessionToForm(conf, "") for conf in q if
                conf.typeOfSession.lower() != "workshop"]
        )


api = endpoints.api_server([ConferenceApi]) # register API
