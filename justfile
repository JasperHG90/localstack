set shell := ["bash", "-uc"]

alias s := setup
alias f := format

format:
    nomad fmt -recursive

setup:
    pre-commit install
