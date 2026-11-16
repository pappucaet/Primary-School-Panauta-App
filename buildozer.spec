[app]
title = Primary School Panauta
package.name = pspanauta
package.domain = org.panauta
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf,xlsx
version = 1.0
requirements = python3,kivy,openpyxl,reportlab,pillow,plyer,android
icon.filename = %(source.dir)s/logo.png
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,CAMERA
android.api = 33
android.ndk = 25b
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
