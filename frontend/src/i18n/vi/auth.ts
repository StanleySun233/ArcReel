import type enAuth from "@/i18n/en/auth";

export default {
  'login': 'Đăng nhập',
  'logging_in': 'Đang đăng nhập...',
  'login_failed': 'Đăng nhập thất bại',
  'login_callback': 'Đang hoàn tất đăng nhập...',
  'login_callback_failed': 'Callback đăng nhập thất bại',
  'camel_login': 'Đăng nhập bằng CaMeL',
  'camel_login_unavailable': 'Chưa cấu hình đăng nhập CaMeL',
  'tenant_switcher_label': 'Chuyển không gian',
  'tenant_switching': 'Đang chuyển...',
  'tenant_switch_failed': 'Không thể chuyển không gian',
  'tenant_personal_badge': 'Không gian cá nhân',
  'tenant_role_admin': 'Quản trị',
  'tenant_role_member': 'Thành viên',
  'tenant_role_view': 'Chỉ xem',
  'username': 'Tên đăng nhập',
  'password': 'Mật khẩu',
} satisfies Record<keyof typeof enAuth, string>;
