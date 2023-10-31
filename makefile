default: run

venv:
	python3 -m venv .venv

install-deps: trackers
	python -m pip install -r requirements.txt 

install-build-deps:
	python -m pip install build twine

install-package:
	pip install -e .

build: clean trackers
	python -m build

check:
	twine check dist/* 

upload:
	twine upload -u passiomatic dist/*

upload-test:
	twine upload -u passiomatic -r testpypi dist/*

trackers:
	curl https://cf.trackerslist.com/best_aria2.txt > videobox/trackers.txt

clean:
	rm -rf dist/ build/

run:
	flask --app videobox --debug run 

run-waitress:
	waitress-serve --host 127.0.0.1 --port 5000 --threads=8 --call videobox:create_app

reset:
	rm ~/.videobox/library.db

shell:
	flask --app videobox shell

sql:
	sqlite3 ~/.videobox/library.db
