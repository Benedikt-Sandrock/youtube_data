import requests

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
r = requests.get(url)

print("Status Code:", r.status_code)
print(r.text[:500])