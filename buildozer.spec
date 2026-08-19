[app]

title = Meditation Timer
package.name = meditationtimer
package.domain = org.yourname

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav,mp3,ogg,json

version = 0.1

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Optional: add your own 512x512 icon.png to this folder and uncomment:
# icon.filename = %(source.dir)s/icon.png

android.permissions = WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
