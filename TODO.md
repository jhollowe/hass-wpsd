# TODO

## WPSD changes needed

Features that cannot be done without modifying WPSD. Nothing identified yet.

## Integration

- Make credentials optional so users who only want the public (unauthenticated) data can skip the username/password.
- Config flow: test host and credentials against WPSD. Needs to know which endpoint is behind the login (the web server auth config is not in the reference repos; WPSD stores the admin password via `htpasswd` for user `pi-star`, i.e. likely HTTP basic auth).
- Work out which data is available without login.
- Decide how to detect short transmissions (fast polling vs. a push mechanism from WPSD).
- Implement client for WPSD-WebCode endpoints.
- Required entities: enabled-mode booleans, active mode sensor, firmware version.
- Nice-to-have: active connections/callsigns, linked network/talkgroup, transmitting boolean.
