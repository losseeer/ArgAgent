import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Debate Arena",
  description: "结构化论辩练习：断言台账 + 矛盾检测 + 透明谬误标注",
};

// §8.2：TopBar 右侧的 BadgeBar 是五类降级/提示角标的唯一挂载点（N8 断言其存在）
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-white text-neutral-900">{children}</body>
    </html>
  );
}
