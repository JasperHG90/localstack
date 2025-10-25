This is a perfect use case for Consul's **External Service Registration**, as it allows you to register services running on nodes (like your Raspberry Pi) that are not running a local Consul agent.

The registration will be performed on your main server (which is running the Consul server) and will point to the MinIO instance on your Raspberry Pi.

Here is the step-by-step process.

---

## 1. Get the Necessary Information

Before you start, you need two pieces of information from your Raspberry Pi (RPI):

1.  **RPI IP Address:** The IP address of the Raspberry Pi on your network (e.g., `192.168.1.50`).
2.  **MinIO Port:** The port MinIO is listening on (default is usually `9000` or `9001` for the API).

## 2. Create the Consul External Service Definition

You will create a JSON file on your server, which will be submitted to the Consul catalog. This file defines both the RPI as an "external node" and the MinIO service running on it.

Create a file named `minio-rpi-external.json` on your server with the following structure.

```json
{
  "Node": "raspberry-pi-minio",
  "Address": "RPI_IP_ADDRESS",
  "Datacenter": "dc1",
  "Service": {
    "ID": "minio-server-rpi",
    "Service": "minio",
    "Port": MINIO_PORT,
    "Address": "RPI_IP_ADDRESS",
    "Tags": ["external", "storage", "rpi"],
    "Check": {
      "Name": "MinIO HTTP Health Check",
      "HTTP": "http://RPI_IP_ADDRESS:MINIO_PORT/minio/health/live",
      "Interval": "10s"
    }
  },
  "NodeMeta": {
    "external-node": "true"
  }
}
```

### **Customize the Variables:**

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `RPI_IP_ADDRESS` | The IP of the Raspberry Pi | `192.168.1.50` |
| `MINIO_PORT` | The port MinIO is running on | `9000` |
| `"Node"` | A unique name for the RPI node in Consul | `"raspberry-pi-minio"` |
| `"Service"` | The common service name for discovery | `"minio"` |
| `Datacenter` | Must match your Consul server's DC | `"dc1"` |
| `"HTTP"` Check Path | MinIO's standard health check endpoint | `http://192.168.1.50:9000/minio/health/live` |

> **Note on Health Check:** MinIO provides a simple HTTP health check at the `/minio/health/live` endpoint. This is an excellent way to verify its availability.

## 3. Register the External Service with Consul

From your main server, you can register the service using the Consul HTTP API via `curl` or the Consul CLI.

Assuming your Consul server is running on `localhost:8500` (which is the default) and the MinIO IP is `192.168.1.50` on port `9000`, run this command on your **main server**:

### Using the Consul CLI (Recommended)

You can use the built-in `consul catalog register` command.

```bash
consul catalog register minio-rpi-external.json
```

### Using cURL (HTTP API)

Alternatively, you can post the JSON directly to the catalog API endpoint.

```bash
curl \
    --request PUT \
    --data @minio-rpi-external.json \
    http://localhost:8500/v1/catalog/register
```

A successful registration will return a response of `true`.

## 4. Verify the Registration and Health Check

Once registered, the MinIO service on the Raspberry Pi will now appear in your Consul catalog.

1.  **Check the Consul UI:** Open your Consul Web UI. You should see a new service named `minio` and a new node named `raspberry-pi-minio`.
2.  **Verify via CLI:** Use the Consul DNS or API to check the service.

    ```bash
    consul members
    # You should see the 'raspberry-pi-minio' node
    
    consul catalog services
    # You should see 'minio' in the list
    ```

3.  **Check Health:** Because you defined a health check, Consul will automatically start performing checks against the MinIO endpoint (`/minio/health/live`) on the Raspberry Pi.

    ```bash
    consul catalog service minio
    ```
    The output will show the service instance and its associated health checks. If MinIO is running and accessible from the server, the check status should eventually switch to `passing`.

By using the **External Service Registration** method, you achieve service discovery for MinIO without needing to install or manage a Consul agent on the Raspberry Pi, honoring your "for reasons" constraint.

TODO: 

- Use a terraform resource: https://registry.terraform.io/providers/hashicorp/consul/latest/docs/resources/service
