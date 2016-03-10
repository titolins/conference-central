# Udacity Full Stack Web Developer Nanodegree
## Conference Organization App

date: 2016-02-22
author: Tito Lins

4th project for the completion of the course.

In this project, we had to develop a cloud based api server for a web based conference organization app.

### Requirements
* Google appengine
* Python

### Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the Developer Console.
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default localhost:8080)
1. Deploy your application.


### Design decisions
In this project, we were required to make certain design decisions to implement
all that was asked.

#### Session kind
We were asked to add sessions to the already implemented conferences. The model
was implemented as detailed below:
```
class Session(ndb.Model):
    """Session -- Session object"""
    # the first and second properties are self explanatory
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty(repeated=True)
    # instead of a speaker property, as suggested by the project description,
    # we chose to use the speaker name, considering that we have implemented a
    # speaker kind. The property name is speakerDisplayName as to clear things.
    speakerDisplayName = ndb.StringProperty()
    # we have implemented duration as an integer representing the duration of
    # the session in minutes (changed back to integer because of previous
    # comment regarding possible 24hrs sessions).
    duration        = ndb.IntegerProperty()
    # type of the session (such as workshop, for example)
    typeOfSession   = ndb.StringProperty()
    # datetime.date() object representing the date of the session.
    date            = ndb.DateProperty()
    # time object representing the time the session will begin.
    startTime       = ndb.TimeProperty()
    # id of the conference it is attached to
    conferenceId    = ndb.IntegerProperty()

class SessionForm(messages.Message):
    """SessionForm -- Session outbound form message"""
    # again, self explanatory
    name            = messages.StringField(1)
    highlights      = messages.StringField(2, repeated=True)
    # the speaker field is a speakerform. In this casa, we kept the name of the
    # property as speaker also to make things easier to understand. The
    # downside of this approach is having to parse yet another field of the
    # session form and creating the speaker by hand.
    speaker         = messages.MessageField('SpeakerForm', 3)
    duration        = messages.IntegerField(4)
    # type of the session (e.g. 'workshop')
    typeOfSession   = messages.StringField(5)
    # in the form class, we chose to receive the date and time fields (which
    # are: date and startTime) as string and parse them into python 
    # date and time objects, respectivelly.
    date            = messages.StringField(6)
    startTime       = messages.StringField(7)
    # urlsafe of the entity key and the id and name of the conference the
    # session is attached to. It's a nice convenience to receive them in the
    # form.
    conferenceId    = messages.IntegerField(8)
    websafeKey      = messages.StringField(9)
    conferenceDisplayName = messages.StringField(10)

class SessionUpdateForm(messages.Message):
    """SessionUpdateForm -- Session inbound form message"""
    # This form was created for the update of the session entities. We have
    # removed the properties that are not to be changed by the user.
    name            = messages.StringField(1)
    highlights      = messages.StringField(2, repeated=True)
    speaker         = messages.MessageField('SpeakerUpdateForm', 3)
    duration        = messages.IntegerField(4)
    typeOfSession   = messages.StringField(5)
    date            = messages.StringField(6)
    startTime       = messages.StringField(7)
```

A Session is added to the datastore having the respective conference as it's
parent. The following required endpoints were implemented regarding Sessions:
```
getConferenceSessions
    Given a conference websafe key, returns all Conference Sessions.
getConferenceSessionsByType
    Returns all Conference Sessions filtered by the supplied type of session.
getSessionsBySpeaker
    Given a speaker urlsafe key, returns all sessions given by the specified
    speaker.
createSession
    We had to make certain assumptions here regarding the date and startTime
    properties. For the first one (date), we assumed we would receive the date
    in the same format provided by the existing frontend when creating a new
    conference (e.g.: '2016-02-11T02:00:00.000Z'). Regarding the startTime,
    however, we simplified things a little bit by assuming the time format
    would only include hour and minutes (e.g.: '15:00') - please note that we
    chose 24hr format for hours.
```
Also in connection with the Session kind, we have implemented the following
endpoints required by task 4 (Add Sessions to User Wishlist):
```
addSessionToWishlist
    Given a session websafe key, adds such session to the authorized user
    wishlist.
getSessionsInWishlist
    Returns all sessions in authorized user wishlist.
deleteSessionInWishlist
    Given a session websafe key, removes a it from authorized user wishlist.
```
Further to the above, we also provide the following endpoints:
```
updateSession
    Allows the session object present in the DataStore to be updated.
    We have defined another form class (SessionUpdateForm) in this case,
    considering that some attributes should not be changed by the user (such as
    the websafeKey). This endpoint may also be used to update the speaker
    entity.
querySessions
    Made in connection with task 3. In order to allow for scalability,
    DataStore was designed in a way that it's performance should only depend on
    the size of the result set and not on the size of all data stored in it. As
    such, DataStore will always use indexes to find matching data. This
    approach imposes a couple of constraints, which are: (i) an inequality
    filter may only be applied to one property; and (ii) a property with an
    inequality filter must be sorted first.
    Thus, this method has been created to allow inequality filtering on many
    properties, besides not requiring any sorting to be applied on the query.
    This method uses the formatAllFilters (based on the formatFilters method
    used in connection with the queryConference method provided) and the
    _doInequalityFilter to format and apply, respectively, the requested
    filters. The filters must have the format described below. Example for
    filtering sessions that are not workshop sessions and with a startTime
    greater than 7pm below:
        {
            "filters":
            [
                {
                    "field": "TYPE",
                    "operator": "NE",
                    "value": "workshop"
                },
                {
                    "field": "START_TIME",
                    "operator": "LE",
                    "value": "19:00"
                }
            ]
        }
    Valid filter operators are:
        (i) 'EQ' for equality ('=');
        (ii) 'GT' for greater than ('>'),
        (iii) 'GTEQ' for greater than or equal to ('>=');
        (iv) 'LT' for less than ('<');
        (v) 'LTEQ' for less than or equal to ('<='); or
        (vi) 'NE' for not equal ('!=').
    Please note that the fields are also translated and are not to be passed as
    defined in the session model. Valid field values for the query are:
        (i) 'HIGHLIGHT' for the 'highlights' model property;
        (ii) 'TYPE' for the 'typeOfSession' model property;
        (iii) 'DATE' for the 'date' model property;
        (iv) 'START_TIME' for the 'startTime' model property; and
        (v) 'DURATION' for the 'duration' model property.
    NOTE: It was a conscient decision to ignore objects with null values when
    applying these filters. For example, if you query by startTime, any
    sessions with a null startTime will not be included in the query result.
    This was the decision that made most sense at the time to avoid the
    TypeErrors caused by comparing to NoneType's.
```

#### Speaker
The Speaker is implemented as a whole entity, which is created at the moment of
the session creation or update. Despite that, the Speaker is not attached as a
child to the Session that created it (considering that a Speaker may have
references to multiple sessions, which is not achievable through relationship
modeling in DataStore).

We solve this be storing a list of the session's keys that this speaker is
related to. When creating an Speaker, we first check to see if it does not
already exists. If it does, we just append the new session to it's list of
sessions. Otherwise, we create a new Speaker and the session key to it's
sessions list.

Regarding the featured speaker implementation, every time a existing speaker is
added to a new session a task is created. This task will check if the speaker
is attached to any other session of the same conference and, if positive, will
save an announcement containing the name of the speaker and of all sessions it
is attached to in that conference to the memcache using the conference urlsafe
key as the memcache key.

Regarding the speaker life flow, we did not provide any api endpoints for
creating or updating a speaker. All of this is achievable through the session
endpoints (both creation and update). The session form contains a speaker form
used both for creating and updating the speakers.

The speaker model and form implementations are detailed below:
```
class Speaker(ndb.Model):
    """Speaker -- Kind model"""
    name            = ndb.StringProperty(required=True)
    specialties     = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    country         = ndb.StringProperty()
    languages       = ndb.StringProperty(repeated=True)
    # I'm afraid this may be the only property that deserves further
    # considerations about. Considering that the speaker may be attached to
    # several sessions, and that a many to one relationship is not achievable
    # in datastore using the entity relationship (as defined for the conference
    # and session models which have profile and conference, respectivelly, as
    # it's ancestors), the obvious option was to create a repeated property
    # with a direct reference to the entities we needed to attach the speaker
    # to. The KeyProperty seemed the best option (holding the keys for the
    # objects themselves are in fact really convenient when we need to retrieve
    # all at once by using ndb.get_multi). The only downside is having to parse
    # this to urlsafe when copying into the SpeakerForm, but did not represent
    # any difficulty simple to do.
    sessions        = ndb.KeyProperty(kind=Session, repeated=True)

class SpeakerForm(messages.Message):
    """SpeakerForm -- outbound speaker message form"""
    name            = messages.StringField(1)
    specialties     = messages.StringField(2, repeated=True)
    city            = messages.StringField(3)
    country         = messages.StringField(4)
    languages       = messages.StringField(5, repeated=True)
    # As said above, the only downside here is having to convert the key
    # objects to urlsafe strings. Other than that, the implementation is pretty
    # straightforward.
    sessions        = messages.StringField(6, repeated=True)
    websafeKey      = messages.StringField(7)

class SpeakerUpdateForm(messages.Message):
    """SpeakerForm -- inbound speaker message form"""
    # This form was created for the update of the speaker entities. We have
    # removed the sessions and websafeKey properties, as these are not to be
    # changed in any case.
    name            = messages.StringField(1)
    specialties     = messages.StringField(2, repeated=True)
    city            = messages.StringField(3)
    country         = messages.StringField(4)
    languages       = messages.StringField(5, repeated=True)
```

The following endpoints regarding this entity have been implemented:

```
getSessionSpeaker
    Given the urlsafe key of a session, returns it's respective speaker.
getFeaturedSpeaker
    Given the urlsafe key of a conference, returns the featured speaker for
    that conference, if any. The conference featured speaker is a speaker which
    is related to more than one session in the given conference.
```

