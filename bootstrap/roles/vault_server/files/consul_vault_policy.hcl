key_prefix "vault/" { policy = "write" }
service "vault" { policy = "write" }
agent_prefix "" { policy = "write" }
session_prefix "" { policy = "write" }
node_prefix "" { policy = "read" }
