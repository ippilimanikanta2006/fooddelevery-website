import requests

# Test credentials
LOGIN_URL = 'http://127.0.0.1:5000/login'
UPLOAD_URL = 'http://127.0.0.1:5000/admin/menu/add'
IMAGE_PATH = r'C:\Users\mytresh\.gemini\antigravity\brain\c9867461-d99a-4704-b86c-f49a1d2e7470\paneer_butter_masala_test_png_1775628246399.png'

session = requests.Session()

# 1. Login
login_data = {
    'username': 'owner',
    'password': 'password'
}
r_login = session.post(LOGIN_URL, data=login_data)
if 'Dashboard' in r_login.text or 'Orders' in r_login.text or r_login.status_code == 200:
    print('Login successful')
else:
    print('Login failed')
    exit(1)

# 2. Upload
with open(IMAGE_PATH, 'rb') as img:
    files = {'image': img}
    data = {
        'name': 'Paneer Butter Masala',
        'price': '320.0',
        'description': 'Rich and creamy cottage cheese in a spiced tomato gravy.'
    }
    r_upload = session.post(UPLOAD_URL, data=data, files=files, allow_redirects=True)
    
    if 'Menu item added successfully!' in r_upload.text:
        print('Upload successful')
    else:
        print('Upload failed')
        print(r_upload.text[:500])
