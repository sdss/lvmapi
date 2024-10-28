# Changelog

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
