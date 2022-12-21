#!/bin/sh

# See https://haim.dev/posts/2020-08-08-python-macos-app/ 

set $APPLICATION_NAME=./kivy-sdk-packager/osx/Videobox.app
codesign -s Developer -v --deep --timestamp --entitlements entitlements.plist -o runtime $APPLICATION_NAME
xcrun altool --store-password-in-keychain-item "AC_PASSWORD" -u $DEVELOPER_USERNAME -p $DEVELOPER_PASSWORD
ditto -c -k --keepParent $APPLICATION_NAME ./kivy-sdk-packager/osx/Videobox.app
xcrun altool --notarize-app -t osx -f ./kivy-sdk-packager/osx/Videobox.app \
    --primary-bundle-id com.passiomatic.videobox -u $DEVELOPER_USERNAME --password "@keychain:AC_PASSWORD"