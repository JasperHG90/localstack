job "nginx" {
  group "frontend" {
    network {
      port "nginx" { to = 80 }
    }

    task "nginx" {
      driver = "podman"
      config {
        image = "docker.io/library/nginx"
        ports = ["nginx"]
      }
    }
  }
}
