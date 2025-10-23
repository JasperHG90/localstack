set shell := ["bash", "-uc"]

alias s := setup
alias f := format
alias p := pre_commit

format:
    nomad fmt -recursive

setup:
    pre-commit install

pre_commit:
    pre-commit run --all-files
