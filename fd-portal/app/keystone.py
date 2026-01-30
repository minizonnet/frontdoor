import requests

class KeystoneClient:
    def __init__(self, keystone_url: str, user_domain: str):
        self.keystone_url = keystone_url.rstrip("/")
        self.user_domain = user_domain

    def validate_password(self, username: str, password: str) -> None:
        """
        Validate Keystone credentials using POST /v3/auth/tokens.
        Success: HTTP 201 and X-Subject-Token header.
        We do NOT store the token (this portal is a gate, not SSO).
        """
        url = f"{self.keystone_url}/auth/tokens"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": username,
                            "domain": {"name": self.user_domain},
                            "password": password,
                        }
                    },
                }
            }
        }

        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 201:
            raise ValueError("Invalid credentials")
        if not r.headers.get("X-Subject-Token"):
            raise ValueError("Missing Keystone token header")
