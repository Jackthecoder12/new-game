[app]
title = Space Invader
package.name = spaceinvader
package.domain = org.spaceinvader
source.dir = .
source.include_exts = py,png,jpg,wav,ogg
source.exclude_dirs = .github, bin, .buildozer
version = 1.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/assets/ufo.png
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
