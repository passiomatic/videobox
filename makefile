all: run

install-deps:
	pip3 install -r requirements.txt 

run: 
	python3 main.py