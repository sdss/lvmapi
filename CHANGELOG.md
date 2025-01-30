# Changelog

## Next version

### ✨ Improved

* Include the `engineering_mode` data in enclosure status response.


## 0.2.7 - 2025-01-26

### 🚀 New

* Added `/overwatcher/reset` route.

### ✨ Improved

* Report alerts in the `/overwatcher/status` route.


## 0.2.6 - 2025-01-14

### 🚀 New

* Log traffic and errors to Sentry.
* Add `/macros/shutdownLCO` endpoint for internal use at LCO.


## 0.2.5 - 2025-01-01

### 🚀 New

* Add `/actors/actor-to-deployment` and `/actors/deployment-to-actors` routes.

### ✨ Improved

* Return `dome_percent_open` in enclosure status endpoint.

### 🏷️ Changed

* Reduce ttl for cache in enclosure endpoints.

### 🔧 Fixed

* Fix a potential case in which sending the night log email would fail if it had not yet been created.


## 0.2.4 - 2025-01-01

This version was yanked due to an issue during the release.


## 0.2.3 - 2024-12-27

### 🔧 Fixed

* Use `lvmopstools` 0.5.5 with fix to the InfluxDB client and install the `slack` extra.
* Add `lvm.spec.fibsel` to list of actors.


## 0.2.2 - 2024-12-27

This version was yanked due to a bug in the InfluxDB client.


## 0.2.1 - 2024-12-27

### 🚀 New

* [#17](https://github.com/sdss/lvmapi/pull/17) Add `/alerts/connectivity` endpoint to check the access to the internet and LCO services from LVM.

## 🏷️ Changed

* [#16](https://github.com/sdss/lvmapi/pull/16) Move `slack` and a lot of the `notifications` code to `lvmopstools`.

### ✨ Improved

* Cache alerts and enclosure status.

### ⚙️ Engineering

* Add initial framework for testing.


## 0.2.0 - 2024-11-30

### ✨ Improved

* Add `/transparency/summary/{telescope}` endpoint.

### ⚙️ Engineering

* Moved code from the schedule, InfluxDB, and weather modules to the `lvmoptools` package.


## 0.1.17 - 2024-11-19

### ✨ Improved

* Add `focusing` and `troubleshooting` fields to `OverwatcherStatusModel`.
* Rename `Time not observing` to `Time not exposing` in the night logs.


## 0.1.16 - 2024-11-17

### ✨ Improved

* Add self-reported Overwatcher comments to the night log.


## 0.1.15 - 2024-11-12

### 🚀 New

* [#14](https://github.com/sdss/lvmapi/pull/14) Add `/transparency` endpoint to retrieve transparency data.

### ✨ Improved

* Switch to using `smtp-02.lco.cl` as mail server.
* Allow to define an external configuration file via the `$LVMAPI_CONFIG_PATH` environment variable.

### 🔧 Fixed

* Correctly calculate time lost in night metrics while the night is ongoing.


## 0.1.14 - 2024-11-11

### 🚀 New

* Added `/logs/night-logs/{mjd}/metrics` endpoint to retrieve metrics for a given night (night length, time lost, efficiency). These data are also included in the night log.

### ✨ Improved

* Allow to update LN2 fill records in the database. Add ``complete`` field to the LN2 fill model.
* Use `Gort.emergency_shutdown()` for the `/macros/shutdown` endpoint.

### 🔧 Fixed

* Fix typo in argument in the shutdown recipe.


## 0.1.13 - 2024-11-10

### 🚀 New

* Create a new router `/notifications` to create and retrieve notifications. New notifications are sent over Slack or email depending on parameters and the notification level.


## 0.1.12 - 2024-11-07

### 🚀 New

* Add the `/logs/notifications/{mjd}` route to retrieve the Overwatcher notifications for a given MJD.
* Add notifications section to night log email and plain-text version.


## 0.1.11 - 2024-11-06

### 🚀 New

* Add `/enclosure/nps` routes to query and set the state of the NPS outlets.

### ✨ Improved

* Add `disable_overwatcher` query parameters to `/macros/shutdown`.


## 0.1.10 - 2024-11-04

### ✨ Improved

* Allow to modify a night log comment.
* Attach full plaintext version of the night log to the email.

### 🏷️ Changed

* Swap the order of the exposure data and software versions in the night log email template.


## 0.1.9 - 2024-10-30

### ✨ Improved

* Added function `is_measurament_safe()` to calculate if weather data values are safe.
* Report actor versions in night log email.

### 🏷️ Changed

* Change `/overwatcher/status/allow_calibrations` to `/overwatcher/status/allow_calibrations`.


## 0.1.8 - 2024-10-28

### 🚀 New

* Add `/macros/cleanup` endpoint.

### 🔧 Fixed

* Prevent the `lvmapi` development version from inheriting production task messages from the exchange.


## 0.1.7 - 2024-10-28

### 🚀 New

* Add the option to stop an actor.

### ✨ Improved

* Allow to pass start and end time to the weather report endpoint.
* Add `overwatcher` to the list of actors.
* Update ephemeris schedule to match LCO's.
* Add overwatcher observing status data to `/overwatcher/status`.
* Add query param to avoid resending night log emails.

### 🔧 Fixed

* Fix `smtp.sendmail()` call in `email_night_log()`.

### ⚙️ Engineering

* Implement system to fake alert values.


## 0.1.6 - 2024-10-10

### ✨ Improved

* Redirect `/enclosure` to `/enclosure/status`.
* Add `?now` query argument to `/overwatcher/disable`.
* Allow setting Slack messsage colour as attachment.


## 0.1.5 - 2024-09-26

### 🚀 New

* Add routes to send night log email and retrieve it as plain text.

### 🏷️ Changed

* Removed the alias `/ephemeris` for `/ephemeris/summary`.


## 0.1.4 - 2024-09-24

### 🚀 New

* Multiple new routes for `/logs/night-logs`.
* Add `/macros/shutdown_from_dupont` route that bypasses authentication as long as the request comes from the DuPont subnet.

### 🏷️ Changed

* By default do not return LN2 fill plots as base64 images.
* Rename base route `/log` to `/logs`.


## 0.1.3 - 2024-09-18

### 🚀 New

* Added endpoints `/spectrograph/fills/{pk}/metadata`, `/spectrograph/fills/list` endpoints.


## 0.1.2 - 2024-09-18

### 🚀 New

* Added endpoints `/spectrograph/fills/running`, `/spectrograph/fills/measurements`, and `/spectrograph/fills/register` with associated functions.

### ✨ Improved

* Improvements to the Slack posting routes.
* Prevent redirects in the `/alerts` endpoint.


## 0.1.1 - 2024-09-13

### 🔧 Fixed

* Update `lvmopstools` to 0.3.5 and use correct name for `spectrograph_status` function.


## 0.1.0 - 2024-09-13 [Yanked]

### 🚀 New

* Initial release.
