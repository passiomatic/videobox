COMMAND=

default: run

venv:
	python3 -m venv .venv

install-deps:
	python -m pip install -r requirements.txt 

install-build-deps:
	python -m pip install build twine

build: clean
	python -m build

check:
	twine check dist/* 

upload:
	twine upload dist/*

upload-test:
	twine upload -r testpypi dist/*

clean:
	rm -rf dist/ build/

run: 
	python3 -m videobox $(COMMAND)
	
sql:
	sqlite3 ~/.videobox/library.db
