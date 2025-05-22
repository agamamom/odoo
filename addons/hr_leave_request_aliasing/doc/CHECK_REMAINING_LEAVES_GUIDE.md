# Hướng dẫn kiểm tra tính năng: Kiểm tra số ngày nghỉ phép còn lại

## Tính năng mới đã thêm

Module `hr_leave_request_aliasing` đã được bổ sung tính năng mới để kiểm tra và theo dõi số ngày nghỉ phép còn lại của nhân viên:

1. **Kiểm tra số ngày nghỉ phép còn lại:**

   - Tự động tính toán số ngày nghỉ phép còn lại cho mỗi loại nghỉ phép
   - Hiển thị số ngày nghỉ còn lại trên giao diện đơn xin nghỉ phép

2. **Cảnh báo khi vượt quá số ngày cho phép:**

   - Hiển thị cảnh báo khi nhân viên yêu cầu nghỉ vượt quá số ngày được phép
   - Hiển thị cảnh báo khi nhân viên sắp hết ngày nghỉ phép (còn ít hơn 3 ngày)

3. **Tự động cập nhật số ngày nghỉ còn lại:**
   - Số ngày nghỉ phép còn lại được tự động cập nhật sau khi đơn được phê duyệt

## Hướng dẫn kiểm tra

### 1. Cài đặt và cấu hình

1. **Cập nhật module:**

   - Đi đến menu `Apps` > tìm kiếm "Open HRMS Leave Request Aliasing"
   - Nhấn nút `Cập nhật` để áp dụng các thay đổi mới
   - Hoặc chạy lệnh: `python odoo-bin -c odoo.conf -d congminhmsi --update=hr_leave_request_aliasing`

2. **Cấu hình phân bổ ngày nghỉ phép:**
   - Đi đến menu `Thời gian nghỉ` > `Phân bổ` > `Tạo phân bổ`
   - Tạo phân bổ ngày nghỉ cho loại "Nghỉ phép năm" với số ngày xác định (ví dụ: 12 ngày)
   - Tạo phân bổ cho một hoặc nhiều nhân viên để kiểm tra

### 2. Kiểm tra tính năng hiển thị số ngày nghỉ còn lại

1. **Kiểm tra trong danh sách đơn nghỉ phép:**

   - Đi đến menu `Thời gian nghỉ` > `Thời gian nghỉ`
   - Xác minh rằng có một cột mới "Số ngày nghỉ còn lại" được hiển thị
   - Cột này có thể được hiển thị/ẩn bằng cách nhấp vào biểu tượng tùy chọn (3 chấm)

2. **Kiểm tra trong form đơn nghỉ phép:**

   - Mở một đơn nghỉ phép hiện có hoặc tạo mới
   - Xác minh rằng trường "Số ngày nghỉ còn lại" được hiển thị sau trường "Loại nghỉ phép"
   - Kiểm tra giá trị hiển thị có chính xác không bằng cách so sánh với số ngày đã phân bổ trừ đi số ngày đã sử dụng

3. **Kiểm tra biểu tượng cảnh báo:**
   - Kiểm tra xem cảnh báo có xuất hiện khi còn ít hơn 3 ngày nghỉ phép không
   - Kiểm tra xem cảnh báo có xuất hiện khi số ngày yêu cầu vượt quá số ngày còn lại không

### 3. Kiểm tra tính năng kiểm tra số ngày nghỉ phép khi tạo đơn mới

1. **Tạo đơn nghỉ phép với số ngày trong hạn mức:**

   - Đi đến menu `Thời gian nghỉ` > `Thời gian nghỉ` > `Tạo mới`
   - Chọn loại nghỉ phép "Nghỉ phép năm" (loại yêu cầu phân bổ)
   - Nhập số ngày nghỉ nhỏ hơn hoặc bằng số ngày còn lại
   - Xác minh rằng đơn được tạo thành công mà không có cảnh báo

2. **Tạo đơn nghỉ phép vượt quá hạn mức:**
   - Tạo một đơn nghỉ phép mới với số ngày nhiều hơn số ngày còn lại
   - Xác minh rằng hệ thống hiển thị thông báo lỗi: "Không đủ ngày nghỉ phép! Bạn đã yêu cầu X ngày cho loại nghỉ phép Y, nhưng chỉ còn lại Z ngày."
   - Xác minh rằng không thể lưu đơn nếu vượt quá số ngày cho phép

### 4. Kiểm tra tính năng tự động kiểm tra qua email

1. **Gửi email xin nghỉ phép trong hạn mức:**

   - Gửi email đến địa chỉ alias (ví dụ: leave@company.com)
   - Tiêu đề: "LEAVE REQUEST - Xin nghỉ phép năm"
   - Nội dung: "Tôi xin nghỉ phép năm. Date From: 10/06/2025 Date To: 11/06/2025" (chọn số ngày trong hạn mức)
   - Xác minh rằng đơn được tạo thành công mà không có cảnh báo trong phần ghi chú (chatter)

2. **Gửi email xin nghỉ phép vượt quá hạn mức:**
   - Gửi email đến địa chỉ alias
   - Tiêu đề: "LEAVE REQUEST - Xin nghỉ phép năm"
   - Nội dung: "Tôi xin nghỉ phép năm. Date From: 10/06/2025 Date To: 31/12/2025" (chọn số ngày vượt quá hạn mức)
   - Xác minh rằng đơn vẫn được tạo (không từ chối) nhưng có ghi chú cảnh báo trong phần chatter: "Đơn này cần được xem xét lại vì vượt quá số ngày nghỉ phép cho phép."

### 5. Kiểm tra tính năng tìm kiếm và lọc

1. **Sử dụng bộ lọc "Vượt quá số ngày cho phép":**
   - Đi đến menu `Thời gian nghỉ` > `Thời gian nghỉ`
   - Sử dụng bộ lọc mới "Vượt quá số ngày cho phép" từ menu tìm kiếm
   - Xác minh rằng chỉ những đơn có số ngày yêu cầu vượt quá số ngày còn lại mới được hiển thị

### 6. Kiểm tra tính năng tự động cập nhật số ngày còn lại

1. **Kiểm tra khi đơn được phê duyệt:**
   - Tạo một đơn nghỉ phép mới
   - Ghi lại số ngày nghỉ còn lại trước khi phê duyệt
   - Phê duyệt đơn (chuyển từ trạng thái "Để phê duyệt" sang "Đã phê duyệt")
   - Xác minh rằng số ngày nghỉ còn lại đã được cập nhật (giảm đi số ngày đã sử dụng)

## Xử lý sự cố

Nếu bạn gặp vấn đề khi kiểm tra tính năng mới, vui lòng thực hiện các bước sau:

1. **Kiểm tra lỗi trong log của Odoo:**

   - Chạy Odoo với tùy chọn `--log-level=debug` để thấy thông tin chi tiết hơn
   - Kiểm tra log để biết lỗi cụ thể liên quan đến `hr_leave` hoặc `remaining_leaves`

2. **Làm mới bộ nhớ cache:**

   - Khởi động lại dịch vụ Odoo để làm mới bộ nhớ cache
   - Xóa bộ nhớ cache trình duyệt và đăng nhập lại

3. **Kiểm tra phân bổ ngày nghỉ:**

   - Xác minh rằng nhân viên đã được phân bổ ngày nghỉ phép
   - Kiểm tra loại nghỉ phép có yêu cầu phân bổ hay không (requires_allocation = 'yes')

4. **Kiểm tra cài đặt quyền người dùng:**
   - Đảm bảo người dùng có quyền xem và chỉnh sửa thông tin nghỉ phép

## Lưu ý

- Tính năng kiểm tra số ngày nghỉ còn lại chỉ áp dụng cho các loại nghỉ phép yêu cầu phân bổ trước (requires_allocation = 'yes').
- Các loại nghỉ phép không yêu cầu phân bổ (requires_allocation = 'no') sẽ không bị hạn chế số ngày.
- Trong đó, loại "Nghỉ phép năm" đã được cấu hình để yêu cầu phân bổ, các loại khác như "Nghỉ ốm", "Nghỉ thai sản", "Nghỉ việc riêng có lương", "Nghỉ lễ, Tết" không yêu cầu phân bổ.
