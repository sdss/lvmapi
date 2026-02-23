# Changelog

## 0.2.21 - 2026-02-23

### ✨ Improved

* Allow dry-run option for manual LN2 fills.


## 0.2.20 - 2026-01-16

### 🚀 New

* Allow manual LN2 fills via the `lvmcryo` web server.


## 0.2.19 - 2025-12-26

### ✨ Improved

* Include enclosure e-stop status in alerts route.

### 🔧 Fixed

* Restrict `taskiq` to `<0.12.0` to avoid a [reload issue](https://github.com/taskiq-python/taskiq/issues/565).
* Fix release GitHub Action to use the correct version of the `pypa/gh-action-pypi-publish` action.


## 0.2.18 - 2025-11-06

### ✨ Improved

* Make `/macros/power_cycle_ag_cameras` endpoint more efficient now that all cameras are powered from PDUs.

### 🔧 Fixed

* Replace `passlib` with `pwdlib` and use `argon2id` for password hashing. `passlib` seems to have stopped working.


## 0.2.17 - 2025-10-25

### ✨ Improved

* Include dither position in exposure data.


## 0.2.16 - 2025-08-29

### ✨ Improved

* Reconnect AG cameras after a power cycle.
* Import the `app` in `get_gort_client` if not passed.
* Increase timeout for some caches and add various caches to `/actors` routes.


## 0.2.15 - 2025-08-10

### ✨ Improved

* Update `lvmopstools` to 0.5.19 to support power cycling AG cameras connected to a NPS.


## 0.2.14 - 2025-08-09

### ✨ Improved

* Change default `taskiq` acknowledgement type to `when_received` in `poe` development script.
* Improve typing in `/spectrographs/ion` endpoint.
* Query only on NPS in `/enclosure/nps/{nps}` instead of commanding all the NPS actors and then selecting the one we want.
* Update `lvmopstools` to 0.5.18.


## 0.2.13 - 2025-06-13

### ✨ Improved

* Use `lvmopstools` 0.5.16 to update the weather API endpoint.

### 🔧 Fixed

* Fix a case in which getting the night log would fail if an airmass was null.


## 0.2.12 - 2025-05-07

### ✨ Improved

* Use `lvmopstools` 0.5.13 to ensure that weather data from the API is fully returned for intervals longer than one hour.
* Increase the lookback interval for weather data to 1.5 hours in alerts to prevent problems with the first data point.
* Report Overwatcher alerts in the `/alerts` endpoint.
* Report `engineering_mode` in `/alerts`.

### 🔧 Fixed

* Fix `dead-letter-routing-key` in `broker.py`.


## 0.2.11 - 2025-04-01

### 🚀 New

* Add route `/overwatcher/calibrations/schedule-long-term`.


## 0.2.10 - 2025-02-27

### 🚀 New

* Add route `/macros/power_cycle_ag_cameras`.
* Add route `/system/ping`.

### ✨ Improved

* Use `is_host_up` from `lvmopstools.utils`.

### 🏷️ Changed

* Dew point alert is raised when the dew point temperature is within 3 degrees of the outside temperature.


## 0.2.9 - 2025-02-03

### ✨ Improved

* Add routes `/enclosure/engineering-mode/disable`, `/enclosure/engineering-mode/enable`, and `/enclosure/engineering-mode/reset-e-stops`.
* Add option `close_dome` to `/overwatcher/status/{mode}`.


## 0.2.8 - 2025-01-30

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
