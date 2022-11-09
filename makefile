all: run

install-deps:
	pip3 install -r requirements.txt 

run: 
	python3 src/main.py

clean:
	rm -rf build dist

build-alias: clean
	python3 setup.py py2app -A

build: clean
	python3 setup.py py2app
