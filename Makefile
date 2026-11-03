.PHONY: make freeze freeze-check lint test check

make:
	python3 scripts/make_dev.py --seed 20261103 --out data/dev.jsonl

freeze:
	python3 scripts/freeze.py

freeze-check:
	python3 scripts/freeze.py --check

lint:
	python3 rubric/lint.py \
		--rubric rubric/rubric.v0.yaml \
		--counterexamples rubric/counterexamples.jsonl

test:
	python3 -m unittest discover -s tests -v

check: lint freeze-check test

.PHONY: reproduce
reproduce:
	python3 scripts/make_dev.py --seed 20261103 --out /tmp/dev.reproduced.jsonl
	cmp data/dev.jsonl /tmp/dev.reproduced.jsonl
	@echo "reproduce OK: 逐字节一致"
