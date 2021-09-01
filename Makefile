run:
	limnopapers --interactive

test:
	pytest -v --ignore=scratch --ignore=build_dashboard.py

dashboard:
	echo dashboard created
	python build_dashboard.py
	pandoc dashboard.md -o dashboard.html	

install:
	pip install --upgrade -e .

keywords:
	git pull && add limnopapers/keywords.csv && git commit -m "stash keywords [skip ci]" && git push