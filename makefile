COMMAND=

default: run

venv:
	python3 -m venv .venv

install-deps: trackers
	python -m pip install -r requirements.txt 

install-build-deps:
	python -m pip install build twine

build: clean trackers
	python -m build

check:
	twine check dist/* 

upload:
	twine upload dist/*

upload-test:
	twine upload -r testpypi dist/*

trackers:
	curl https://cdn.staticaly.com/gh/XIU2/TrackersListCollection/master/best_aria2.txt > videobox/trackers.txt

clean:
	rm -rf dist/ build/

run: 
	python3 -m videobox $(COMMAND)
	
sql:
	sqlite3 ~/.videobox/library.db
