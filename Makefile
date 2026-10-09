PYTHON ?= python3
IMAGE ?= office-trace-bench:runtime
CONFIG ?= /root/.openclaw

.PHONY: image list test regression tlc opm
image:
	docker build -t $(IMAGE) -f runtime/Dockerfile .
list:
	$(PYTHON) office.py list
test:
	$(PYTHON) -m unittest discover -s tests -v
regression:
	$(PYTHON) scripts/regression.py
tlc:
	$(PYTHON) office.py run --kind xlsx --dataset tlc --image $(IMAGE) --config $(CONFIG)
opm:
	$(PYTHON) office.py run --kind pdf --dataset opm --image $(IMAGE) --config $(CONFIG)
