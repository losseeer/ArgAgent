/** @type {import('next').NextConfig} */
// 前端默认直连 backend；app/api/ 只是预留的可选 BFF 转发层，故此处无 rewrite。
const nextConfig = {
  reactStrictMode: true,
};

module.exports = nextConfig;
