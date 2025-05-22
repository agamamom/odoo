# Hướng dẫn cài đặt và cấu hình module hr_leave_request_aliasing

## Yêu cầu hệ thống

- Odoo 18.0
- Các module phụ thuộc:
  - `hr_holidays`: Quản lý nghỉ phép (mặc định trong Odoo)
  - `hr_payroll_community`: Quản lý lương cộng đồng
  - `mail`: Hệ thống email (mặc định trong Odoo)

## Cài đặt

### Phương pháp 1: Cài đặt từ Odoo Apps

1. Đăng nhập vào Odoo với quyền Quản trị hệ thống
2. Vào menu **Apps**
3. Bỏ chọn lọc "Apps" (nếu có)
4. Tìm kiếm "Open HRMS Leave Request Aliasing"
5. Nhấn cài đặt

### Phương pháp 2: Cài đặt thủ công

1. Tải mã nguồn từ Github hoặc từ nguồn cung cấp
2. Giải nén và đặt thư mục `hr_leave_request_aliasing` vào đường dẫn addons của Odoo
3. Khởi động lại Odoo server
4. Đăng nhập vào Odoo với quyền Quản trị hệ thống
5. Vào menu **Apps**
6. Bỏ chọn lọc "Apps" (nếu có)
7. Nhấn nút "Cập nhật danh sách ứng dụng"
8. Tìm kiếm "Open HRMS Leave Request Aliasing"
9. Nhấn cài đặt

## Cấu hình cơ bản

### Thiết lập Email Alias

1. Đi đến menu **Cài đặt** > **Kỹ thuật** > **Email** > **Aliases**
2. Tìm alias `hr.holidays` và chỉnh sửa nếu cần
3. Đảm bảo rằng "Chuyển hướng đến" được đặt là "Leave Request"
4. Lưu thay đổi

### Cấu hình loại nghỉ phép

Module này tự động tạo các loại nghỉ phép phổ biến ở Việt Nam:

- Nghỉ phép năm
- Nghỉ ốm (hưởng BHXH)
- Nghỉ thai sản (hưởng BHXH)
- Nghỉ việc riêng có lương
- Nghỉ lễ, Tết

Bạn có thể kiểm tra và chỉnh sửa các loại nghỉ phép này tại:

1. Đi đến menu **Nghỉ phép** > **Cấu hình** > **Loại nghỉ phép**
2. Kiểm tra và chỉnh sửa các loại nghỉ phép nếu cần

## Ủy quyền người dùng

Để sử dụng đầy đủ tính năng của module, người dùng cần có các quyền sau:

1. Quản lý nghỉ phép

   - Nhóm: Human Resources / Officer hoặc Manager

2. Quản lý BHXH

   - Nhóm: Human Resources / Officer hoặc Manager

3. Quản lý lương
   - Nhóm: Human Resources / Officer hoặc Manager

Để cấp quyền cho người dùng:

1. Đi đến menu **Cài đặt** > **Người dùng & Công ty** > **Người dùng**
2. Chọn người dùng cần cấp quyền
3. Trong tab **Quyền truy cập**, đảm bảo người dùng thuộc vào nhóm phù hợp

## Kiểm tra cài đặt

Sau khi cài đặt:

1. Đi đến menu **Nhân viên** và mở thông tin một nhân viên
2. Kiểm tra xem tab "Thông tin BHXH" đã xuất hiện chưa
3. Tạo mới một đơn nghỉ phép loại "Nghỉ ốm" và kiểm tra xem phần "Thông tin BHXH" có hiển thị không

## Xử lý sự cố

Nếu gặp vấn đề khi cài đặt hoặc sử dụng module:

1. Kiểm tra log lỗi của Odoo (thường ở `/var/log/odoo/` hoặc tùy theo cấu hình)
2. Đảm bảo tất cả các module phụ thuộc đã được cài đặt
3. Đảm bảo người dùng có đủ quyền truy cập
4. Nếu cần hỗ trợ thêm, vui lòng liên hệ đội phát triển
