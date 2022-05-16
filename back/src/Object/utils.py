import re

class Utils:
    def json_email_replace(json, modifiers = [{"func": lambda x: str(x), "res": [1]}, {"func": lambda x: str(x), "res": [0]}]):
        regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if isinstance(json, str) and (re.fullmatch(regex, json)):
            done1 = True
            temp_json1 = json
            for modifier in modifiers:
                temp_json1 = modifier['func'](json)
                temp_json2 = temp_json1
                done2 = True
                for i in modifier['res']:
                    try:
                        temp_json2 = temp_json2[i]
                    except:
                        done2 = False
                        break
                if not done2:
                    done1 = False
                    break
                temp_json1 = temp_json2
            if done1:
                json = temp_json1
        elif isinstance(json, list):
            for idx, elem in enumerate(json):
                if any(isinstance(elem, type) for type in [dict, list, str]):
                    json[idx] = Utils.json_email_replace(elem, modifiers)
        elif isinstance(json, dict):
            for elem in json:
                if any(isinstance(json[elem], type) for type in [dict, list, str]):
                    json[elem] = Utils.json_email_replace(json[elem], modifiers)
        return json
