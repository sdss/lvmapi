# Changelog

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
