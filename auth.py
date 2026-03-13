import requests

class AuthSession:

    def __init__(self, base, user, token):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (user, token)

    def get(self, url):
        r = self.session.get(self.base + url)
        r.raise_for_status()
        return r.json()

    def post(self, url, data):
        r = self.session.post(self.base + url, data=data)
        r.raise_for_status()
        return r.json()
