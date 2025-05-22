# Hướng dẫn kiểm thử BHXH trong module hr_leave_request_aliasing

## 1. Thiết lập thông tin BHXH cho nhân viên

1. Đăng nhập vào Odoo với quyền Quản lý nhân sự
2. Đi đến menu Nhân viên > Nhân viên
3. Chọn một nhân viên bất kỳ để mở form chi tiết
4. Chuyển đến tab "Thông tin BHXH"
5. Nếu nhân viên chưa có thông tin BHXH, nhấn nút "Tạo thông tin BHXH"
6. Điền các thông tin sau:
   - Mã số BHXH (ví dụ: VN1234567890)
   - Ngày tham gia (ví dụ: 01/01/2023)
   - Mức lương cơ bản BHXH (ví dụ: 10,000,000 VND)
   - Đảm bảo tích chọn "Đang hoạt động"
7. Nhấn Lưu

## 2. Kiểm tra tính năng tạo đơn nghỉ ốm có BHXH

1. Đi đến menu Nghỉ phép > Yêu cầu nghỉ phép
2. Tạo yêu cầu nghỉ phép mới
3. Chọn nhân viên đã thiết lập BHXH ở bước 1
4. Chọn loại nghỉ phép là "Nghỉ ốm"
5. Đặt ngày bắt đầu và kết thúc (ví dụ: 3 ngày)
6. Xác nhận và lưu đơn
7. Kiểm tra:
   - Trường "Được hưởng BHXH" phải được tự động đánh dấu
   - Trường "Loại trợ cấp BHXH" phải hiển thị là "Ốm đau"
   - Trường "Trợ cấp BHXH" phải được tự động tính toán (75% lương cơ bản)

## 3. Kiểm tra tính năng tạo đơn nghỉ thai sản có BHXH

1. Tạo yêu cầu nghỉ phép mới
2. Chọn một nhân viên nữ đã thiết lập BHXH
3. Chọn loại nghỉ phép là "Nghỉ thai sản"
4. Đặt ngày bắt đầu và kết thúc (ví dụ: 180 ngày)
5. Xác nhận và lưu đơn
6. Kiểm tra:
   - Trường "Được hưởng BHXH" phải được tự động đánh dấu
   - Trường "Loại trợ cấp BHXH" phải hiển thị là "Thai sản"
   - Trường "Trợ cấp BHXH" phải được tự động tính toán (100% lương cơ bản)

## 4. Kiểm tra tính năng tích hợp với bảng lương

1. Đi đến menu Bảng lương > Bảng lương
2. Tạo bảng lương mới cho nhân viên đã có đơn nghỉ ốm/thai sản đã được phê duyệt
3. Đặt kỳ lương bao gồm khoảng thời gian nghỉ phép
4. Tính toán bảng lương
5. Kiểm tra:
   - Tab "BHXH" phải hiển thị các khoản trợ cấp BHXH tương ứng
   - Nếu là nghỉ ốm, "Trợ cấp ốm đau" phải hiển thị số tiền chính xác (75% lương cơ bản x số ngày nghỉ)
   - Nếu là nghỉ thai sản, "Trợ cấp thai sản" phải hiển thị số tiền chính xác (100% lương cơ bản x số ngày nghỉ)
   - "Tổng khấu trừ lương do nghỉ phép" phải hiển thị chính xác (tiền lương - tiền trợ cấp)

## 5. Kiểm tra tính năng nhận diện loại nghỉ phép từ email

1. Thiết lập email alias cho nghỉ phép (nếu chưa có)
2. Gửi email đến địa chỉ alias với nội dung:
   - Tiêu đề: "Đơn xin nghỉ ốm"
   - Nội dung: "Tôi xin nghỉ ốm từ 01/11/2023 đến 05/11/2023 do bị cảm cúm"
3. Đi đến menu Nghỉ phép > Yêu cầu nghỉ phép
4. Kiểm tra:
   - Có đơn nghỉ phép mới được tạo tự động
   - Loại nghỉ phép được nhận diện chính xác là "Nghỉ ốm"
   - Ngày bắt đầu và kết thúc được nhận diện chính xác

## Các lưu ý khi kiểm thử

- Đảm bảo nhân viên đã được thiết lập đầy đủ thông tin BHXH trước khi kiểm thử
- Các loại nghỉ phép "Nghỉ ốm" và "Nghỉ thai sản" phải được cấu hình sẵn trong hệ thống
- Đối với tính năng email, cần thiết lập đúng alias và địa chỉ email của nhân viên
- Nhân viên phải có hợp đồng lao động và lương cơ bản để tính toán trợ cấp BHXH

## Các tình huống phổ biến cần kiểm tra

1. **Nghỉ ốm ngắn ngày**: 1-3 ngày, kiểm tra mức trợ cấp 75%
2. **Nghỉ ốm dài ngày**: 15-30 ngày, kiểm tra mức trợ cấp 75%
3. **Nghỉ thai sản đủ**: 180 ngày, kiểm tra mức trợ cấp 100%
4. **Nghỉ thai sản ngắn**: 90 ngày, kiểm tra mức trợ cấp 100%
5. **Nghỉ phép không thuộc BHXH**: Kiểm tra không có trợ cấp BHXH
