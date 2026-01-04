

import requests

app_client_id = mssparkutils.credentials.getSecret(f"https://{key_vault_name}.vault.azure.net/", kvclientid_1)

app_client_secret = mssparkutils.credentials.getSecret(f"https://{key_vault_name}.vault.azure.net/", kvclientkey_1)

microsoft_tenant_id = mssparkutils.credentials.getSecret(f"https://{key_vault_name}.vault.azure.net/", kvtenantid_1)

microsoft_subscription_id = mssparkutils.credentials.getSecret(f"https://{key_vault_name}.vault.azure.net/", subscription_id)