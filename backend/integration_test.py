import requests

def run_integration_check():
    base_url = "http://127.0.0.1:8000"
    try:
        health = requests.get(base_url, timeout=5)
        print(f"IT-01 Health Check: {health.status_code}")
    except:
        print("IT-01 Health Check: FAILED")

    bad_login = requests.post(f"{base_url}/auth/login", 
                              json={"email": "hacker@test.com", "password": "123"})
    print(f"IT-03 Security Logic: {bad_login.status_code}")

if __name__ == "__main__":
    run_integration_check()