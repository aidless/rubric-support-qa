.PHONY: make freeze freeze-check testset testset-check disagreement disagreement-check lint requirements test check

make:
	python3 scripts/make_dev.py --seed 20261103 --out data/dev.jsonl

freeze:
	python3 scripts/freeze.py

freeze-check:
	python3 scripts/freeze.py --check

testset:
	python3 scripts/make_test.py --seed 20261104 --out data/test.jsonl
	python3 scripts/freeze_test.py

testset-check:
	python3 scripts/freeze_test.py --check

disagreement:
	python3 scripts/make_disagreement.py

disagreement-check:
	python3 scripts/make_disagreement.py --check

lint:
	python3 rubric/lint.py \
		--rubric rubric/rubric.v0.yaml \
		--counterexamples rubric/counterexamples.jsonl

requirements:
	python3 scripts/check_requirements.py \
		--requirements requirements.md \
		--rubric rubric/rubric.v0.yaml

test:
	python3 -m unittest discover -s tests -v

check: lint requirements freeze-check testset-check disagreement-check test

.PHONY: reproduce
reproduce:
	python3 scripts/make_dev.py --seed 20261103 --out /tmp/dev.reproduced.jsonl
	cmp data/dev.jsonl /tmp/dev.reproduced.jsonl
	python3 scripts/make_test.py --seed 20261104 --out /tmp/test.reproduced.jsonl
	cmp data/test.jsonl /tmp/test.reproduced.jsonl
	python3 scripts/make_disagreement.py --out /tmp/disagreement.reproduced.jsonl
	cmp data/disagreement.pool.jsonl /tmp/disagreement.reproduced.jsonl
	@echo "reproduce OK: 逐字节一致"
