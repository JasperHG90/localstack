# Unseal the Vault using the unseal keys.
# Plan:
#  1. Check if VAULT_UNSEAL_KEY_1, VAULT_UNSEAL_KEY_2, VAULT_UNSEAL_KEY_3, VAULT_ADDR and VAULT_TOKEN are set.
#  2. If not set, exit with error.
#  3. If set, run vault operator unseal command three times with the respective keys.
if [ -z "$VAULT_UNSEAL_KEY_1" ] || [ -z "$VAULT_UNSEAL_KEY_2" ] || [ -z "$VAULT_UNSEAL_KEY_3" ] || [ -z "$VAULT_ADDR" ] || [ -z "$VAULT_TOKEN" ]; then
  echo "Error: VAULT_UNSEAL_KEY_1, VAULT_UNSEAL_KEY_2, VAULT_UNSEAL_KEY_3, VAULT_ADDR and VAULT_TOKEN must be set."
  exit 1
fi

vault operator unseal "$VAULT_UNSEAL_KEY_1"
vault operator unseal "$VAULT_UNSEAL_KEY_2"
vault operator unseal "$VAULT_UNSEAL_KEY_3"
