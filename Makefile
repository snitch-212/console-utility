export PYTHONDONTWRITEBYTECODE = 1
export PYTHONPATH = src

.PHONY: run test

run:
	python3 -m depgraph $(ARGS)

test:
	python3 -m unittest discover -s tests -v
