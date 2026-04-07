import requests
import numpy as np

vec=[0.1]*384

r=requests.post("http://127.0.0.1:6001/search",json={"vector":vec})
print(r.json())
