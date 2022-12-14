default: run

venv:
	python3 -m virtualenv .venv

install-deps:
	pip3 install -r requirements.txt 

run: 
	python3 run.py

clean:
	rm -rf icon.icns icon.iconset build

build: clean build-icon 
	./build.sh

sql:
	sqlite3 library.db

sql-drop-torrents:
	sqlite3 library.db "drop table torrent;"

build-icon:
	mkdir icon.iconset
	sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
	sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
	sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
	sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
	sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
	sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
	sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
	cp icon.png icon.iconset/icon_512x512@2x.png
	iconutil -c icns icon.iconset	
