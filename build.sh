#!/bin/sh

git clone https://github.com/kivy/kivy-sdk-packager.git
pushd kivy-sdk-packager/osx

curl -O -L https://github.com/kivy/kivy/releases/download/2.1.0/Kivy.dmg

hdiutil attach Kivy.dmg -mountroot .
cp -R Kivy/Kivy.app Videobox.app

./fix-bundle-metadata.sh Videobox.app -n Videobox -v "0.1.0" -a "Videobox" -o "com.passiomatic.videobox" -i "../../videobox/icon.png"

pushd Videobox.app/Contents/Resources/venv/bin
source activate
popd

pip3 install -r ../../requirements.txt
#pip3 install ../,,/videobox
deactivate

./cleanup-app.sh Videobox.app

# pushd Videobox.app/Contents/Resources/
# ln -s ./venv/bin/videobox yourapp
# popd

./relocate.sh Videobox.app
./create-osx-dmg.sh Videobox.app Videobox

popd
echo "Build done."
