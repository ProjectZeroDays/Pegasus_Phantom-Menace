install:
	pip install -e .

apply:
	python scripts/apply_bundle.py bundle.txt . 

test:
	python -m pytest -q 

verify:
	python scripts/verify.py 

smoke:
	bash scripts/smoke.sh 
