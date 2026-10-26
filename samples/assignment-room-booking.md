Assignment 3: Campus Room Booking API

Context

Students at a fictional university of applied sciences struggle to find a free project room. Today they write their name on a paper list at the reception desk, and double bookings happen every week. Your team builds a small web API in Python that shows which rooms are free and lets students book one.

What the team delivers

- A Python web API (Flask or FastAPI) that starts locally with one command
- Endpoints to list the rooms, see a room's bookings for one day, book a room for a time slot, and cancel a booking
- Rooms and bookings stored in a SQLite database, with a script that fills it with a few example rooms
- Automated tests that run with pytest
- A README that explains how to install, start and test the API

Grading criteria

Working features (40%): All four endpoints work as described and return clear JSON, with a helpful error message when the input is wrong.
Booking rules (20%): A room can't be booked twice for overlapping times, and a booking must fall within opening hours (08:00 to 22:00) and can't be in the past.
Tests (20%): The tests cover the endpoints and the booking rules, including at least one overlapping booking, and they all pass.
Code quality and documentation (20%): The code is split into clear modules with readable names, and with the README a teammate can run the project within ten minutes.
