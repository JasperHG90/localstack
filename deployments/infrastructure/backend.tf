terraform {
  backend "consul" {
    address = "localstack.local:8500"
    path    = "terraform/infrastructure"
    schem   = "http"
  }
}
