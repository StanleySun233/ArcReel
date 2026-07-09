import type enAuth from '../en/auth';

export default {
  'login': '登录',
  'logging_in': '登录中...',
  'login_failed': '登录失败',
  'login_callback': '正在完成登录...',
  'login_callback_failed': '登录回调失败',
  'camel_login': '通过 CaMeL 登录',
  'camel_login_unavailable': 'CaMeL 登录未配置',
  'username': '用户名',
  'password': '密码',
} satisfies Record<keyof typeof enAuth, string>;
