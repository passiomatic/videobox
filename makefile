default: run-debug

venv:
	python3 -m venv .venv

install-deps: trackers
	python -m pip install -r requirements.txt 

install-build-deps:
	python -m pip install build twine py2app rumps

install-package:
	pip install -e .

build: clean trackers
	python -m build

check:
	twine check dist/* 

upload:
	twine upload dist/*

upload-test:
	twine upload -r testpypi dist/*

trackers:
	curl https://cf.trackerslist.com/best_aria2.txt > videobox/trackers.txt

clean:
	rm -rf dist build

run:
	flask --app videobox run 

run-debug:
	flask --app videobox --debug run 

run-waitress:
	waitress-serve --host 127.0.0.1 --port 5000 --threads=8 --call videobox:create_app

reset:
	rm ~/.videobox/library.db

shell:
	flask --app videobox shell

sql:
	sqlite3 ~/.videobox/library.db

# macOS app build

build-app-alias: clean build-icon
	python setup-app.py py2app -A	

build-app: clean build-icon
	python setup-app.py py2app

run-app:
	./dist/Videobox.app/Contents/MacOS/Videobox

build-icon:
	mkdir -p build/icon.iconset
	sips -z 16 16     macos/icon.png --out build/icon.iconset/icon_16x16.png
	sips -z 32 32     macos/icon.png --out build/icon.iconset/icon_16x16@2x.png
	sips -z 32 32     macos/icon.png --out build/icon.iconset/icon_32x32.png
	sips -z 64 64     macos/icon.png --out build/icon.iconset/icon_32x32@2x.png
	sips -z 128 128   macos/icon.png --out build/icon.iconset/icon_128x128.png
	sips -z 256 256   macos/icon.png --out build/icon.iconset/icon_128x128@2x.png
	sips -z 256 256   macos/icon.png --out build/icon.iconset/icon_256x256.png
	cp macos/icon.png build/icon.iconset/icon_512x512@2x.png
	iconutil -c icns build/icon.iconset