import requests

# Url to obtain bearer token
uri = f"https://login.microsoftonline.com/{microsoft_tenant_id}/oauth2/token"


# Required parameters to properly obtain the bearer token
data = {'client_id':app_client_id,
        'grant_type':'client_credentials',
        'client_secret':app_client_secret,
        'resource':'https://management.core.windows.net'}

# API call to get bearer token
response = requests.post(uri, data = data)
response = response.json()

# Set variables from api call to access_token and token_type
ms_token_type = response.get('token_type', None)
token = response.get('access_token', None)

#display(token)
