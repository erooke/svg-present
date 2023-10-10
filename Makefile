source := $(shell find src -type f -name "*.py")

.PHONY: format
format:
	black $(source)
	isort --profile=black $(source)
