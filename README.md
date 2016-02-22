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

* Session kind
We were asked to add sessions to the already implemented conferences. As such,
we implemented not only the Session model, but also the SessionForm and
SessionForms.

A Session is added to the datastore having the respective conference as it's
parent. The following required endpoints were implemented regarding Sessions:
```
getConferenceSessions
	Returns all Conference Sessions.
getConferenceSessionsByType
	Returns all Conference Sessions filtered by the supplied type of session.
getSessionsBySpeaker
	Returns all sessions given by the specified speaker.
createSession
	We had to make certain assumptions here regarding the date and startTime
	properties, as per the comments present in the code.
```
Also in connection with the Session kind, we have implemented the following
endpoints required by task 4 (Add Sessions to User Wishlist):
```
addSessionToWishlist
    Adds the given session to the authorized user wishlist.
getSessionsInWishlist
    Returns all sessions in authorized user wishlist.
deleteSessionInWishlist
    Removes a given session from authorized user wishlist.
```
Further to the above, we also provide the following endpoints:
```
updateSession
	Allows the session object present in the DataStore to be updated.
	We have defined another form class (SessionUpdateForm) in this case,
	considering that some attributes should not be changed by the user (such as
	the websafeKey).
querySessions
	Made in connection with task 5. This method uses the formatAllFilters
	(based on the formatFilters method used in connection with the
	queryConference method provided) and the _doInequalityFilter to apply as
	many inequality filters as required by the user. We chose to filter the
	query objects in memory, to surpass DataStore's limitation of one
	inequality filter.
```

Also, in connection with task 6 (add a task), the 'speaker' property is
required for creating a new session and, therefore, may not be left blank.

* Speaker
The Speaker is implemented as a whole entity, which is created at the moment of
the session creation (but may be updated after this moment). Despite that, the
Speaker is not attached as a child to the Session that created it (considering
that a Speaker may have references to multiple sessions, which is not
achievable through relationship modeling in DataStore).

We solve this be storing a list of the session's keys that this speaker is
related to. When creating an Speaker, we first check to see if it does not
already exists. If it does, we just append the new session to it's list of
sessions. Otherwise, we create a new Speaker and the session key to it's
sessions list.

The following endpoints regarding this entity have been implemented:

```
getSessionSpeaker
    Given the urlsafe key of a session, returns it's respective speaker.
getFeaturedSpeaker
    Returns the current featured speaker, as per required in task 6.
```

