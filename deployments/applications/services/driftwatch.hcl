### driftwatch: the daily canary that measures retrieval quality.
###
### It dials embark DIRECTLY, not through Bifrost. The gateway drops
### `input_type`, and that field picks the model's query prefix over its
### document prefix -- a bi-encoder embedded with the wrong one retrieves
### worse and says nothing. The gateway path stays measured from the other
### side: OpenViking's own embedding-call metrics are the same models through
### Bifrost.
###
### Runs on radxa rather than the Jetson. embark's firewall already admits
### 192.168.2.50 on port 8000 (local.firewall_rules.embark), and leaving the
### Jetson to serve models keeps the canary off the node it measures.
job "driftwatch" {
  datacenters = ["localstack"]
  type        = "service"
  namespace   = "default"

  group "driftwatch" {
    constraint {
      attribute = "$${attr.unique.hostname}"
      value     = "${driftwatch_hostname}"
    }

    network {
      port "http" {
        static = 8010
      }
    }

    ### Holds one file: the reference vectors every run after the first is
    ### compared against. Deleting it is how an operator says "this model is
    ### the new normal" after a deliberate model change -- the next run seeds
    ### a fresh baseline and reports no drift until the run after that.
    volume "driftwatch_data" {
      type      = "host"
      source    = "driftwatch_data"
      read_only = false
    }

    task "driftwatch" {
      driver = "podman"

      vault {}

      service {
        name    = "driftwatch"
        port    = "http"
        address = "${driftwatch_host}"

        ### "prometheus" is what puts this on the shared consul_services
        ### scrape job (infrastructure/services/prometheus.hcl), which is the
        ### whole point of the service.
        tags = ["http", "prometheus", "monitoring", "retrieval"]

        ### /healthz, not a readiness probe. The first canary run takes
        ### minutes against a cold embark cache, and a check that waited for
        ### it would restart the task into the same wait forever -- the same
        ### reason embark's own check probes /healthz.
        check {
          name     = "driftwatch alive"
          type     = "http"
          port     = "http"
          path     = "/healthz"
          method   = "GET"
          interval = "30s"
          timeout  = "3s"
        }
      }

      config {
        image        = "${driftwatch_image}"
        ports        = ["http"]
        network_mode = "host"
      }

      volume_mount {
        volume      = "driftwatch_data"
        destination = "/var/lib/driftwatch"
      }

      env {
        DRIFTWATCH_EMBARK_URL          = "${embark_url}"
        DRIFTWATCH_EMBEDDING_MODEL     = "${embedding_model}"
        DRIFTWATCH_RERANK_MODEL        = "${rerank_model}"
        DRIFTWATCH_GOLDSET_PATH        = "/local/goldset.jsonl"
        DRIFTWATCH_RERANK_GOLDSET_PATH = "/local/rerank-goldset.jsonl"
        DRIFTWATCH_BASELINE_PATH       = "/var/lib/driftwatch/baseline.npz"
        DRIFTWATCH_EMBARK_KEY_FILE     = "/secrets/embark.key"

        ### Daily. The blog this follows recommends the same cadence, and the
        ### cost argument here is embark's cache: it keys on a fingerprint of
        ### the served model artifact, so a second run against the same model
        ### is answered from Redis. Only a model change costs GPU time.
        DRIFTWATCH_INTERVAL_SECONDS = "86400"

        ### How many candidates the embedding stage hands the reranker in the
        ### `pipeline` stage. Ten, matching the recall@10 the embedding stage
        ### reports, so the two numbers describe the same shortlist. It does
        ### NOT size the `rerank` stage's pool, which is fixed per row in
        ### rerank-goldset.jsonl and is the whole reason that stage can be read
        ### independently of the embedder.
        DRIFTWATCH_RERANK_POOL = "10"

        ### Generous on purpose: a cold cache means 60 embeddings and up to
        ### 30 rerank calls against a Jetson that may still be warming.
        DRIFTWATCH_REQUEST_TIMEOUT = "120"

        PORT = "8010"
      }

      ### driftwatch's OWN copy of embark's `read` key. The nomad-workloads
      ### role grants a job read only under secret/data/<namespace>/<job_id>/*,
      ### so reading embark's own path would 403. Same copy-under-the-consumer
      ### shape bifrost_hermes_key and bifrost_openviking_key already use.
      ###
      ### Not an env file: the key is read from disk on every run, so a
      ### rotated credential is picked up at the next canary rather than
      ### needing a restart.
      template {
        data = <<-EOF
        {{- with secret "${embark_key_secret}" }}{{ .Data.data.api_key }}{{ end }}
        EOF

        destination = "secrets/embark.key"
      }

      ### The canary set, from services/driftwatch/goldset.jsonl. Rendered in
      ### rather than baked into the image, so changing which queries are
      ### watched is a terraform apply -- the same reason dash takes
      ### tiles.json and embark takes models.json this way.
      ###
      ### Changing it changes the corpus, which invalidates the stored
      ### baseline. driftwatch notices that on its own (the file records how
      ### many documents it was written against) and re-seeds.
      template {
        data = <<-EOF
${goldset}
        EOF

        destination = "local/goldset.jsonl"
        change_mode = "restart"
      }

      ### The rerank canary set: one fixed candidate pool per query, from
      ### services/driftwatch/rerank-goldset.jsonl.
      ###
      ### Separate from the set above because it answers a different question.
      ### The `pipeline` stage reranks whatever the embedder shortlisted, so a
      ### number that moves there could be either model. This pool is the same
      ### ten documents every run whatever the embedder does, which is what
      ### lets a rerank regression be told apart from an embedding one. It also
      ### carries the hard negative embark hand-authored for each query, the
      ### adjacent plausible wrong answer a cross-encoder exists to reject.
      ###
      ### Unlike the baseline, changing this file invalidates nothing: the
      ### stage holds no state between runs.
      template {
        data = <<-EOF
${rerank_goldset}
        EOF

        destination = "local/rerank-goldset.jsonl"
        change_mode = "restart"
      }

      ### Small: 60 documents of 768 floats is under a megabyte, and numpy is
      ### the only heavy import. The work is waiting on embark, not computing.
      resources {
        cpu    = 200
        memory = 384
      }
    }
  }
}
