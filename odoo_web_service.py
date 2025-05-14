# import xmlrpc.client

# # Thông tin kết nối
# url = 'http://localhost:8070'
# db = 'LansingApp'
# username = 'dathoang31082001@gmail.com'
# password = '31082001Dat!'

# # Bước 1: Kết nối với endpoint /xmlrpc/2/common để lấy thông tin version và xác thực
# common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))

# # Lấy thông tin version của Odoo
# version = common.version()
# print("Odoo Server Details: ", version)

# # Xác thực để lấy UID
# uid = common.authenticate(db, username, password, {})
# if uid:
#     print("Authentication successful, UID: ", uid)
# else:
#     print("Authentication failed. Check your username, password, or database name.")
#     exit()

# # Bước 2: Kết nối với endpoint /xmlrpc/2/object để truy vấn dữ liệu
# models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

# # Tìm kiếm danh sách nhân viên (hr.employee)
# employee_ids = models.execute_kw(db, uid, password, 'hr.employee', 'search', [[]])
# print("Employee IDs: ", employee_ids)

# # Lấy thông tin chi tiết của nhân viên (tên, chức vụ)
# if employee_ids:
#     employees = models.execute_kw(db, uid, password, 'hr.employee', 'read', [employee_ids], {'fields': ['name', 'job_title']})
#     print("Employees: ", employees)
# else:
#     print("No employees found.")


import requests

url = 'http://localhost:8070/api/hr/employees'
headers = {
    'API-Key': '76fadb72-2630-447e-8dda-55e66a0de72b'
}
params = {
    'limit': 100,
    'offset': 0
}

response = requests.get(url, headers=headers, params=params)
if response.status_code == 200:
    print("Employees: ", response.json())
else:
    print("Error: ", response.status_code, response.text)