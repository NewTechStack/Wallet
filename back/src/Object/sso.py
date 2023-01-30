import requests
import json
import jwt
import uuid
from tinydb import TinyDB, Query

db = TinyDB('/db.json')
sso_front = "https://sso.rocketbonds.me"
sso_back = "https://api.sso.rocketbonds.me"
apitoken = "690a9b618c8442f992b7496aa09e2c99"
registry_id = "ff000fef-2f52-4867-89ad-df534ca600e0"

class Sso:
    def __init__(self):
        self.apitoken = ""
        self.user = None

    def get_url(self):
        response = requests.request(
            "POST",
            f"{sso_back}/extern/key",
            headers = {
              'Content-Type': 'application/json'
            },
            data = json.dumps(
                {
                  "apitoken": apitoken,
                  "valid_until": 600,
                  "redirect": "https://wallet.newtechstack.fr/login"
                }
            )
        )
        data = json.loads(response.text)
        if not 'data' in data or data['data'] is None:
            return [False, "Error connecting to sso api", 500]
        data = data['data']
        key = data["key"]
        auth = data["auth"]
        id = str(uuid.uuid4())
        data['id'] = id
        db.insert(data)
        url = f"{sso_front}/sso/extern/{key}/{auth}/accept"
        return [True, {"url": url, "id": id}, None]

    def get_token(self, id):
        r = Query()
        res = db.search(r.id == id)
        db.remove(r.id == id)
        if len(res) != 1:
            return [False, "Invalid id", 404]
        key = res[0]['key']
        secret = res[0]['secret']
        response = requests.request(
            "POST",
            f"{sso_back}/extern/key/{key}/token",
            headers = {
              'Content-Type': 'application/json'
            },
            data = json.dumps(
                {
                  "apitoken": apitoken,
                  "secret": secret
                }
            )
        )
        data = json.loads(response.text)
        token = data['data']['usrtoken']
        return self.__decode(token)

    def verify(self, token):
        res = self.__decode(token, get_data = True)
        if not res[0]:
            return res
        self.user = res[1]["data"]["payload"]
        return [True, {}, None]

    def user_by_email(self, email):
        """invite + get user_id"""
        response = requests.request(
            "POST",
            f"{sso_back}/extern/user/invite",
            headers = {
              'Content-Type': 'application/json'
            },
            data = json.dumps(
                {
                  "email": email,
                  "apitoken": apitoken,
                }
            )
        )
        data = json.loads(response.text)
        usr_id = data['data']['usrid']
        return [True, {'id': usr_id}, None]

    def __decode(self, token, get_data = False):
        url = f"{sso_back}/extern/public"
        payload = json.dumps({
          "apitoken": apitoken,
        })
        headers = {
          'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        public_key = json.loads(response.text)['data']['public_key']
        try:
            data = jwt.decode(
                token,
                public_key,
                leeway=0,
                issuer="auth:back",
                audience=f"auth:{registry_id}",
                algorithms=['RS256']
            )
        except jwt.ExpiredSignatureError:
            return [False, "Signature expired", 403]
        except jwt.InvalidSignatureError:
            return  [False, "Invalid signature", 400]
        except jwt.InvalidIssuedAtError:
            return [False, "Invalid time", 400]
        except jwt.InvalidIssuerError:
            return [False, "Invalid issuer", 403]
        except jwt.InvalidAudienceError:
            return [False, "Invalid audience", 401]
        except jwt.ImmatureSignatureError:
            return [False, "Invalid time", 400]
        except jwt.DecodeError:
            return [False, "Invalid jwt", 400]
        if get_data == True:
            return [True, {"data": data}, None]
        return [True, {"usrtoken": token}, None, {"usrtoken": token}]
