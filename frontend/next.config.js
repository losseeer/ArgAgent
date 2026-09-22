/** @type {import('next').NextConfig} */
// 多数情况前端直连 backend（§4 的 app/api 是可选 BFF），故此处无 rewrite。
const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
