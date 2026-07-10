import type enAuth from '../en/auth';

export default {
  'login': '登录',
  'logging_in': '登录中...',
  'login_failed': '登录失败',
  'login_callback': '正在完成登录...',
  'login_callback_failed': '登录回调失败',
  'camel_login': '通过 CaMeL 登录',
  'camel_login_unavailable': 'CaMeL 登录未配置',
  'tenant_switcher_label': '切换空间',
  'tenant_switching': '切换中...',
  'tenant_switch_failed': '切换空间失败',
  'tenant_personal_badge': '个人空间',
  'tenant_role_admin': '管理员',
  'tenant_role_member': '成员',
  'tenant_role_view': '只读',
  'username': '用户名',
  'password': '密码',
} satisfies Record<keyof typeof enAuth, string>;
