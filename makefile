all: run

install-deps:
	pip3 install -r requirements.txt 

run: 
	python3 src/main.py

clean:
	rm -rf build dist cache download icon.iconset

build-alias: clean buid-icon
	python3 setup.py py2app -A

build: clean buid-icon
	python3 setup.py py2app

sql-log-last:
	sqlite3 library.db "select * from synclog order by id desc limit 5;"

sql:
	sqlite3 library.db

buid-icon:
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