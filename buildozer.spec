[app]
title = Invoice Extractor
package.name = invoiceextractor
package.domain = com.personal.invoiceextractor
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt
version = 0.1.0
requirements = python3,kivy,pillow,openpyxl,pyjnius
orientation = portrait
fullscreen = 0

android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.gradle_dependencies = com.google.mlkit:text-recognition:16.0.1
android.add_src = src
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
