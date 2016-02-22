#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT

class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName     = ndb.StringProperty()
    mainEmail       = ndb.StringProperty()
    teeShirtSize    = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    sessionWishlist = ndb.StringProperty(repeated=True)

class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName     = messages.StringField(1)
    teeShirtSize    = messages.EnumField('TeeShirtSize', 2)

class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName     = messages.StringField(1)
    mainEmail       = messages.StringField(2)
    teeShirtSize    = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)
    sessionWishlist = messages.StringField(5, repeated=True)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6) #DateTimeField()
    month           = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate         = messages.StringField(10) #DateTimeField()
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)

class ConferenceUpdateForm(messages.Message):
    """ConferenceUpdateForm -- Conference inbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    topics          = messages.StringField(3, repeated=True)
    city            = messages.StringField(4)
    startDate       = messages.StringField(5) #DateTimeField()
    month           = messages.IntegerField(6, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(7, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(8, variant=messages.Variant.INT32)
    endDate         = messages.StringField(9) #DateTimeField()

class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)

class Session(ndb.Model):
    """Session -- Session object"""
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty(repeated=True)
    speaker         = ndb.StringProperty(required=True)
    duration        = ndb.IntegerProperty()
    typeOfSession   = ndb.StringProperty()
    date            = ndb.DateProperty()
    startTime       = ndb.TimeProperty()
    conferenceId    = ndb.IntegerProperty()

class SessionForm(messages.Message):
    """SessionForm -- Session outbound form message"""
    name            = messages.StringField(1)
    highlights      = messages.StringField(2, repeated=True)
    speaker         = messages.StringField(3)
    duration        = messages.IntegerField(4)
    typeOfSession   = messages.StringField(5)
    date            = messages.StringField(6)
    startTime       = messages.StringField(7)
    conferenceId    = messages.IntegerField(8)
    websafeKey      = messages.StringField(9)
    conferenceDisplayName = messages.StringField(10)

class SessionUpdateForm(messages.Message):
    """SessionUpdateForm -- Session inbound form message"""
    name            = messages.StringField(1)
    highlights      = messages.StringField(2, repeated=True)
    duration        = messages.IntegerField(3)
    typeOfSession   = messages.StringField(4)
    date            = messages.StringField(5)
    startTime       = messages.StringField(6)

class SessionForms(messages.Message):
    """SessionForms -- holder for several session outbound forms"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

class Speaker(ndb.Model):
    """Speaker -- Kind model"""
    name            = ndb.StringProperty(required=True)
    specialties     = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    country         = ndb.StringProperty()
    languages       = ndb.StringProperty(repeated=True)
    sessions        = ndb.KeyProperty(kind=Session, repeated=True)

class SpeakerForm(messages.Message):
    """SpeakerForm -- outbound speaker message form"""
    name            = messages.StringField(1)
    specialties     = messages.StringField(2, repeated=True)
    city            = messages.StringField(3)
    country         = messages.StringField(4)
    languages       = messages.StringField(5, repeated=True)
    sessions        = messages.StringField(6, repeated=True)
    websafeKey      = messages.StringField(7)
    sessionDisplayName = messages.StringField(8)

class SpeakerUpdateForm(messages.Message):
    """SpeakerForm -- inbound speaker message form"""
    name            = messages.StringField(1)
    specialties     = messages.StringField(2, repeated=True)
    city            = messages.StringField(3)
    country         = messages.StringField(4)
    languages       = messages.StringField(5, repeated=True)

class SpeakerForms(messages.Message):
    """SessionForms -- holder for several session outbound forms"""
    items = messages.MessageField(SpeakerForm, 1, repeated=True)

class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
    """
        ConferenceQueryForms
        ---------------------
        multiple ConferenceQueryForm inbound form message

    """
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)
