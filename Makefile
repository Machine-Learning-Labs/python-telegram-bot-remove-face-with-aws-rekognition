.PHONY: setup check deploy destroy

setup:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt

run:
	@echo "Running bot..."
	python3 --version
	python3 src/bot.py

check:
	@echo "Checking dependencies..."
	@which pip >/dev/null || (echo "pip not found. Please install pip."; exit 1)
	@which python >/dev/null || (echo "python not found. Please install Python."; exit 1)

deploy:
	@echo "Deploying infrastructure..."
	terraform init
	terraform plan
	terraform apply

destroy:
	@echo "Destroying Terraform infrastructure..."
	terraform destroy
